"""Historial en SQLite: personas, trabajos, votos, retos y estado del estudio."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS personas (
    token TEXT PRIMARY KEY,
    alias TEXT NOT NULL,
    creado REAL NOT NULL,
    bloqueado INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trabajos (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    alias TEXT NOT NULL,
    prompt TEXT NOT NULL,
    estilo TEXT NOT NULL,
    formato TEXT NOT NULL,
    prompt_final TEXT NOT NULL,
    semilla INTEGER NOT NULL,
    estado TEXT NOT NULL,
    creado REAL NOT NULL,
    inicio REAL,
    fin REAL,
    error TEXT,
    oculto INTEGER NOT NULL DEFAULT 0,
    miniatura_estilo TEXT
);
CREATE TABLE IF NOT EXISTS votos (
    trabajo TEXT NOT NULL,
    token TEXT NOT NULL,
    creado REAL NOT NULL,
    PRIMARY KEY (trabajo, token)
);
CREATE TABLE IF NOT EXISTS retos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    inicio REAL NOT NULL,
    fin_creacion REAL,
    fase TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS estado (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

# Columnas añadidas después de la primera versión (se crean solas en bases de datos antiguas).
COLUMNAS_NUEVAS = {
    "trabajos": {
        "tema": "TEXT",
        "foto": "TEXT",
        "fuerza": "REAL",
        "publico": "INTEGER NOT NULL DEFAULT 1",
        "ancho": "INTEGER",
        "alto": "INTEGER",
        "reto": "INTEGER",
    },
}

INDICES = """
CREATE INDEX IF NOT EXISTS trabajos_token ON trabajos (token, creado);
CREATE INDEX IF NOT EXISTS trabajos_estado ON trabajos (estado, fin);
CREATE INDEX IF NOT EXISTS trabajos_reto ON trabajos (reto);
CREATE INDEX IF NOT EXISTS votos_token ON votos (token);
"""

# Imágenes que se ven en la galería de la clase y en el proyector
VISIBLES = "t.estado = 'hecho' AND t.miniatura_estilo IS NULL AND t.oculto = 0 AND t.publico = 1"


class BaseDatos:
    def __init__(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(ESQUEMA)
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            existentes = {f["name"] for f in self.con.execute(f"PRAGMA table_info({tabla})")}
            for columna, tipo in columnas.items():
                if columna not in existentes:
                    self.con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        self.con.executescript(INDICES)
        self.lock = threading.Lock()

    def _todas(self, sql: str, *args) -> list[dict]:
        with self.lock:
            return [dict(f) for f in self.con.execute(sql, args).fetchall()]

    def _una(self, sql: str, *args) -> dict | None:
        filas = self._todas(sql, *args)
        return filas[0] if filas else None

    def _ejecutar(self, sql: str, *args) -> int:
        with self.lock:
            return self.con.execute(sql, args).lastrowid

    # Estado del estudio
    def leer_estado(self, clave: str, defecto: str) -> str:
        fila = self._una("SELECT valor FROM estado WHERE clave = ?", clave)
        return fila["valor"] if fila else defecto

    def guardar_estado(self, clave: str, valor: str):
        self._ejecutar("INSERT OR REPLACE INTO estado (clave, valor) VALUES (?, ?)", clave, valor)

    # Personas
    def crear_persona(self, token: str, alias: str):
        self._ejecutar("INSERT INTO personas (token, alias, creado) VALUES (?, ?, ?)", token, alias, time.time())

    def persona(self, token: str) -> dict | None:
        return self._una("SELECT * FROM personas WHERE token = ?", token)

    def bloquear(self, token: str, bloqueado: bool):
        self._ejecutar("UPDATE personas SET bloqueado = ? WHERE token = ?", int(bloqueado), token)

    def bloqueados(self) -> list[dict]:
        return self._todas("SELECT token, alias FROM personas WHERE bloqueado = 1 ORDER BY alias")

    # Trabajos
    def crear_trabajo(self, t: dict):
        columnas = ", ".join(t)
        huecos = ", ".join("?" for _ in t)
        self._ejecutar(f"INSERT INTO trabajos ({columnas}) VALUES ({huecos})", *t.values())

    def trabajo(self, id_: str) -> dict | None:
        return self._una(
            "SELECT t.*, (SELECT COUNT(*) FROM votos v WHERE v.trabajo = t.id) AS votos FROM trabajos t WHERE t.id = ?",
            id_,
        )

    def actualizar(self, id_: str, **campos):
        asignaciones = ", ".join(f"{k} = ?" for k in campos)
        self._ejecutar(f"UPDATE trabajos SET {asignaciones} WHERE id = ?", *campos.values(), id_)

    def pendientes(self) -> list[dict]:
        return self._todas("SELECT * FROM trabajos WHERE estado IN ('cola', 'generando') ORDER BY creado")

    def de_persona(self, token: str, limite: int = 60) -> list[dict]:
        return self._todas(
            "SELECT t.*, (SELECT COUNT(*) FROM votos v WHERE v.trabajo = t.id) AS votos FROM trabajos t "
            "WHERE t.token = ? AND t.estado = 'hecho' AND t.miniatura_estilo IS NULL ORDER BY t.fin DESC LIMIT ?",
            token, limite,
        )

    def galeria(self, limite: int, *, panel: bool = False, antes: float | None = None,
                reto: int | None = None, por_votos: bool = False, token: str = "") -> list[dict]:
        """Imágenes terminadas con sus votos. El panel ve también las ocultas y las privadas."""
        sql = (
            "SELECT t.*, (SELECT COUNT(*) FROM votos v WHERE v.trabajo = t.id) AS votos, "
            "EXISTS (SELECT 1 FROM votos v WHERE v.trabajo = t.id AND v.token = ?) AS votado "
            "FROM trabajos t WHERE "
        )
        args: list = [token]
        sql += "t.estado = 'hecho' AND t.miniatura_estilo IS NULL" if panel else VISIBLES
        if antes is not None:
            sql += " AND t.fin < ?"
            args.append(antes)
        if reto is not None:
            sql += " AND t.reto = ?"
            args.append(reto)
        sql += " ORDER BY votos DESC, t.fin ASC" if por_votos else " ORDER BY t.fin DESC"
        sql += " LIMIT ?"
        args.append(limite)
        return self._todas(sql, *args)

    def estadisticas(self) -> dict:
        return self._una(
            "SELECT COUNT(*) AS hechas, COUNT(DISTINCT token) AS personas FROM trabajos "
            "WHERE estado = 'hecho' AND miniatura_estilo IS NULL"
        ) or {"hechas": 0, "personas": 0}

    def duraciones_recientes(self, n: int = 10) -> list[float]:
        filas = self._todas(
            "SELECT fin - inicio AS d FROM trabajos WHERE estado = 'hecho' AND inicio IS NOT NULL "
            "ORDER BY fin DESC LIMIT ?",
            n,
        )
        return [f["d"] for f in filas if f["d"] and f["d"] > 0]

    # Votos
    def votar(self, trabajo: str, token: str, valor: bool) -> int:
        if valor:
            self._ejecutar("INSERT OR IGNORE INTO votos (trabajo, token, creado) VALUES (?, ?, ?)", trabajo, token, time.time())
        else:
            self._ejecutar("DELETE FROM votos WHERE trabajo = ? AND token = ?", trabajo, token)
        return self._una("SELECT COUNT(*) AS n FROM votos WHERE trabajo = ?", trabajo)["n"]

    # Retos
    def reto_activo(self) -> dict | None:
        return self._una("SELECT * FROM retos WHERE fase != 'cerrado' ORDER BY id DESC LIMIT 1")

    def crear_reto(self, titulo: str, fin_creacion: float | None) -> int:
        self._ejecutar("UPDATE retos SET fase = 'cerrado' WHERE fase != 'cerrado'")
        return self._ejecutar(
            "INSERT INTO retos (titulo, inicio, fin_creacion, fase) VALUES (?, ?, ?, 'creando')",
            titulo, time.time(), fin_creacion,
        )

    def fase_reto(self, id_: int, fase: str):
        self._ejecutar("UPDATE retos SET fase = ? WHERE id = ?", fase, id_)

    def imagenes_reto(self, id_: int) -> int:
        return self._una(f"SELECT COUNT(*) AS n FROM trabajos t WHERE t.reto = ? AND {VISIBLES}", id_)["n"]
