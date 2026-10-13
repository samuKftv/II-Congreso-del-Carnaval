"""Ollama simulado: /api/tags y /api/chat, para probar el intérprete de ideas sin IA de verdad."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request


def crear_ollama_falso(modelo: str = "qwen2.5:3b", retardo: float = 0.0) -> FastAPI:
    app = FastAPI()
    app.state.recibidos = []

    @app.get("/api/tags")
    async def tags():
        return {"models": [{"name": modelo}]}

    @app.post("/api/chat")
    async def chat(request: Request):
        cuerpo = await request.json()
        app.state.recibidos.append(cuerpo)
        await asyncio.sleep(retardo)
        idea = cuerpo["messages"][-1]["content"]
        if "PROHIBIDO" in idea:  # el intérprete se pasa de la raya: hay que pintar la idea tal cual
            return {"message": {"role": "assistant", "content": "A nude person"}}
        return {"message": {"role": "assistant", "content": f'<think>pienso</think> "A vivid carnival scene of {idea}."'}}

    return app
