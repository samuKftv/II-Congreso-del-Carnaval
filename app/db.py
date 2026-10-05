"""Historial en SQLite: personas, trabajos y estado del estudio."""

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
CREATE INDEX IF NOT EXISTS trabajos_token ON trabajos (token, creado);
CREATE INDEX IF NOT EXISTS trabajos_estado ON trabajos (estado, fin);
CREATE TABLE IF NOT EXISTS estado (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


class BaseDatos:
    def __init__(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(ESQUEMA)
        self.lock = threading.Lock()

    def _todas(self, sql: str, *args) -> list[dict]:
        with self.lock:
            return [dict(f) for f in self.con.execute(sql, args).fetchall()]

    def _una(self, sql: str, *args) -> dict | None:
        filas = self._todas(sql, *args)
        return filas[0] if filas else None

    def _ejecutar(self, sql: str, *args):
        with self.lock:
            self.con.execute(sql, args)

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
        return self._una("SELECT * FROM trabajos WHERE id = ?", id_)

    def actualizar(self, id_: str, **campos):
        asignaciones = ", ".join(f"{k} = ?" for k in campos)
        self._ejecutar(f"UPDATE trabajos SET {asignaciones} WHERE id = ?", *campos.values(), id_)

    def pendientes(self) -> list[dict]:
        return self._todas("SELECT * FROM trabajos WHERE estado IN ('cola', 'generando') ORDER BY creado")

    def de_persona(self, token: str, limite: int = 60) -> list[dict]:
        return self._todas(
            "SELECT * FROM trabajos WHERE token = ? AND estado = 'hecho' AND miniatura_estilo IS NULL "
            "ORDER BY fin DESC LIMIT ?",
            token, limite,
        )

    def galeria(self, limite: int, incluir_ocultas: bool = False, antes: float | None = None) -> list[dict]:
        sql = "SELECT * FROM trabajos WHERE estado = 'hecho' AND miniatura_estilo IS NULL"
        args: list = []
        if not incluir_ocultas:
            sql += " AND oculto = 0"
        if antes is not None:
            sql += " AND fin < ?"
            args.append(antes)
        sql += " ORDER BY fin DESC LIMIT ?"
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
