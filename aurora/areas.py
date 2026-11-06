"""Áreas comuns lidas de `dados/areas.json`. A taxa decide a confirmação."""

from __future__ import annotations

import json
import unicodedata

from aurora.config import DADOS


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(
        caractere
        for caractere in normalizado
        if unicodedata.category(caractere) != "Mn"
    )


def carregar_areas() -> dict[str, dict]:
    brutas = json.loads((DADOS / "areas.json").read_text(encoding="utf-8"))
    return {area["id"]: area for area in brutas}


AREAS = carregar_areas()

_ALIASES = {
    "salao-de-festas": "salao-de-festas",
    "salao de festas": "salao-de-festas",
    "salao": "salao-de-festas",
    "churrasqueira": "churrasqueira",
    "quadra": "quadra",
    "quadra poliesportiva": "quadra",
}


def resolver_area(texto: str) -> str | None:
    chave = _sem_acento(texto)
    if chave in AREAS:
        return chave
    return _ALIASES.get(chave)
