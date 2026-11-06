"""Tools do especialista de visitantes.

Autorizar libera entrada no prédio, então a tool só grava quando
`tool_confirmation.confirmed` chega pela rota de confirmações.
"""

from __future__ import annotations

from google.adk.tools.tool_context import ToolContext

from aurora import store


def _apartamento(tool_context: ToolContext) -> str:
    return str(tool_context.state["apartamento"])


def listar_meus_visitantes(tool_context: ToolContext) -> dict:
    """Lista os visitantes autorizados do morador desta sessão.

    Returns:
        Visitantes deste apartamento, cada um com nome e data.
    """
    return {"visitantes": store.listar_visitantes(_apartamento(tool_context))}


def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict:
    """Pede confirmação e só então autoriza a entrada do visitante.

    Args:
        nome: Nome de quem vai entrar.
        data: Data da visita no formato AAAA-MM-DD.

    Returns:
        A pendência, a recusa, ou a autorização gravada.
    """
    confirmacao = tool_context.tool_confirmation
    if not confirmacao:
        tool_context.request_confirmation(
            hint=(
                f"Confirme a entrada de {nome} em {data}. "
                "O texto da conversa não autoriza a entrada."
            ),
            payload={"nome": nome, "data": data},
        )
        return {"status": "aguardando_confirmacao", "nome": nome, "data": data}
    if not confirmacao.confirmed:
        return {
            "status": "recusada",
            "mensagem": "A entrada do visitante não foi confirmada.",
        }
    store.autorizar_visitante(_apartamento(tool_context), nome.strip(), data)
    return {"status": "autorizado", "nome": nome.strip(), "data": data}
