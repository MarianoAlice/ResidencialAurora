"""Tools do especialista de reservas.

O apartamento sai de `tool_context.state["apartamento"]`, gravado na criação
da sessão. Nenhuma tool declara parâmetro de apartamento.
"""

from __future__ import annotations

from google.adk.tools.tool_context import ToolContext

from aurora.areas import AREAS, resolver_area
from aurora import store


def _apartamento(tool_context: ToolContext) -> str:
    return str(tool_context.state["apartamento"])


def listar_minhas_reservas(tool_context: ToolContext) -> dict:
    """Lista as reservas ativas do morador desta sessão.

    Returns:
        Reservas deste apartamento, cada uma com codigo, area e data.
    """
    reservas = store.listar_reservas(_apartamento(tool_context))
    return {"reservas": reservas}


def consultar_disponibilidade(area: str, data: str) -> dict:
    """Diz se a área está livre ou ocupada na data.

    Args:
        area: Id da área, como salao-de-festas, churrasqueira ou quadra.
        data: Data no formato AAAA-MM-DD.

    Returns:
        Apenas livre ou ocupada. Sem código, apartamento ou morador.
    """
    area_id = resolver_area(area)
    if area_id is None:
        return {"disponibilidade": "area_desconhecida"}
    if store.data_ocupada(area_id, data):
        return {"disponibilidade": "ocupada"}
    return {"disponibilidade": "livre"}


def cancelar_minha_reserva(area: str, data: str, tool_context: ToolContext) -> dict:
    """Cancela a reserva ativa deste morador na área e data. Não pede confirmação.

    Args:
        area: Id da área, como salao-de-festas, churrasqueira ou quadra.
        data: Data no formato AAAA-MM-DD.

    Returns:
        O cancelamento, ou o aviso de que não há essa reserva para o morador.
    """
    area_id = resolver_area(area)
    if area_id is None:
        return {
            "status": "inexistente",
            "mensagem": "Não há essa reserva no seu apartamento.",
        }
    resultado = store.cancelar(_apartamento(tool_context), area_id, data)
    if not resultado["ok"]:
        return {
            "status": "inexistente",
            "mensagem": "Não há essa reserva no seu apartamento.",
        }
    return {
        "status": "cancelada",
        "codigo": resultado["codigo"],
        "area": resultado["area"],
        "data": resultado["data"],
    }


def reservar_area(area: str, data: str, tool_context: ToolContext) -> dict:
    """Reserva a área na data para o morador desta sessão.

    Área com taxa maior que zero só é gravada depois da confirmação do ADK.
    Área com taxa zero é gravada na hora. A data ocupa no máximo um morador.

    Args:
        area: Id da área, como salao-de-festas, churrasqueira ou quadra.
        data: Data no formato AAAA-MM-DD.

    Returns:
        A reserva criada, a pendência de confirmação, ou a recusa se a data está ocupada.
    """
    area_id = resolver_area(area)
    if area_id is None:
        return {"status": "area_desconhecida", "mensagem": "Área desconhecida."}

    taxa = float(AREAS[area_id]["taxa"])
    if taxa > 0:
        confirmacao = tool_context.tool_confirmation
        if not confirmacao:
            if store.data_ocupada(area_id, data):
                return {
                    "status": "ocupada",
                    "mensagem": "Essa data está ocupada.",
                }
            tool_context.request_confirmation(
                hint=(
                    f"Confirme a reserva de {area_id} em {data}. "
                    "A reserva só é gravada depois desta confirmação."
                ),
                payload={"area": area_id, "data": data},
            )
            return {
                "status": "aguardando_confirmacao",
                "area": area_id,
                "data": data,
            }
        if not confirmacao.confirmed:
            return {
                "status": "recusada",
                "mensagem": "A reserva não foi confirmada.",
            }

    resultado = store.reservar(_apartamento(tool_context), area_id, data)
    if not resultado["ok"]:
        return {
            "status": "ocupada",
            "mensagem": "Essa data acabou de ser ocupada.",
        }
    return {
        "status": "reservada",
        "codigo": resultado["codigo"],
        "area": area_id,
        "data": data,
    }
