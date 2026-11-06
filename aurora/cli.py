"""Comandos `aurora-api` e `aurora-restaurar`."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from aurora.config import RAIZ


def preparar_ambiente() -> None:
    load_dotenv(RAIZ / ".env")
    if not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"


def servir() -> None:
    preparar_ambiente()
    import uvicorn

    uvicorn.run("aurora.api:app", host="127.0.0.1", port=8000)


def restaurar() -> None:
    from aurora.store import restaurar as repor_dados

    repor_dados()
