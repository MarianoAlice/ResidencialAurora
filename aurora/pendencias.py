"""Pendências de confirmação lidas dos eventos da sessão ADK."""

from __future__ import annotations

from typing import Any

from google.adk.flows.llm_flows.functions import (
    REQUEST_CONFIRMATION_FUNCTION_CALL_NAME,
)


def _chamadas(evento: Any) -> list[Any]:
    obter = getattr(evento, "get_function_calls", None)
    if obter is None:
        return []
    return list(obter() or [])


def _respostas(evento: Any) -> list[Any]:
    obter = getattr(evento, "get_function_responses", None)
    if obter is None:
        return []
    return list(obter() or [])


def _detalhes(acao: str, payload: dict[str, Any]) -> dict[str, str]:
    if acao == "autorizar_visitante":
        return {
            "nome": str(payload.get("nome", "")),
            "data": str(payload.get("data", "")),
        }
    return {
        "area": str(payload.get("area", "")),
        "data": str(payload.get("data", "")),
    }


def listar_pendentes(eventos: list[Any]) -> list[dict[str, Any]]:
    """Confirmações pedidas e ainda sem function response."""
    respondidas: set[str] = set()
    pedidos: list[tuple[Any, Any]] = []
    for evento in eventos:
        for resposta in _respostas(evento):
            if (
                resposta.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME
                and resposta.id
            ):
                respondidas.add(resposta.id)
        for chamada in _chamadas(evento):
            if (
                chamada.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME
                and chamada.id
            ):
                pedidos.append((evento, chamada))

    pendentes: list[dict[str, Any]] = []
    for evento, chamada in pedidos:
        if chamada.id in respondidas:
            continue
        args = chamada.args or {}
        original = args.get("originalFunctionCall") or {}
        confirmacao = args.get("toolConfirmation") or {}
        payload = confirmacao.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        acao = str(original.get("name") or "")
        pendentes.append(
            {
                "id": chamada.id,
                "acao": acao,
                "detalhes": _detalhes(acao, payload),
                "payload": payload,
                "invocation_id": getattr(evento, "invocation_id", None),
            }
        )
    return pendentes


def para_resposta(pendentes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": item["id"], "acao": item["acao"], "detalhes": item["detalhes"]}
        for item in pendentes
    ]
