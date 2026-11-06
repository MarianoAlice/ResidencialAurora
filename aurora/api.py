"""API HTTP do Residencial Aurora."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from pydantic import BaseModel, Field

from aurora.agentes import aplicacao
from aurora.cli import preparar_ambiente
from aurora.config import APP_NAME, BANCO_SESSOES, USER_ID
from aurora.pendencias import (
    REQUEST_CONFIRMATION_FUNCTION_CALL_NAME,
    listar_pendentes,
    para_resposta,
)
from aurora import store

_runner: Runner | None = None
_sessoes: DatabaseSessionService | None = None


class PedidoSessao(BaseModel):
    apartamento: str = Field(min_length=1)


class PedidoMensagem(BaseModel):
    texto: str


class PedidoConfirmacao(BaseModel):
    id: str = Field(min_length=1)
    confirmado: bool


def _url_sessoes() -> str:
    BANCO_SESSOES.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite+aiosqlite:///" + BANCO_SESSOES.resolve().as_posix()


def _texto_do_evento(evento: Any) -> str:
    conteudo = getattr(evento, "content", None)
    if conteudo is None or not conteudo.parts:
        return ""
    return "".join(parte.text or "" for parte in conteudo.parts if parte.text)


async def _obter_sessao(session_id: str) -> Any:
    assert _sessoes is not None
    return await _sessoes.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )


async def _executar(
    session_id: str,
    mensagem: types.Content,
    invocation_id: str | None = None,
) -> dict[str, Any]:
    assert _runner is not None
    kwargs: dict[str, Any] = {
        "user_id": USER_ID,
        "session_id": session_id,
        "new_message": mensagem,
    }
    if invocation_id:
        kwargs["invocation_id"] = invocation_id
    textos: list[str] = []
    async for evento in _runner.run_async(**kwargs):
        texto = _texto_do_evento(evento).strip()
        if texto:
            textos.append(texto)
    sessao = await _obter_sessao(session_id)
    pendentes = listar_pendentes(sessao.events if sessao else [])
    return {
        "resposta": "\n".join(textos),
        "confirmacoes_pendentes": para_resposta(pendentes),
    }


@asynccontextmanager
async def _vida(app: FastAPI):
    global _runner, _sessoes
    preparar_ambiente()
    store.garantir_carregado()
    _sessoes = DatabaseSessionService(db_url=_url_sessoes())
    _runner = Runner(app=aplicacao, session_service=_sessoes)
    yield
    _runner = None
    _sessoes = None


app = FastAPI(title="Residencial Aurora", lifespan=_vida)


@app.post("/sessoes", status_code=201)
async def criar_sessao(pedido: PedidoSessao) -> dict[str, str]:
    assert _sessoes is not None
    sessao = await _sessoes.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"apartamento": pedido.apartamento},
    )
    return {"session_id": sessao.id}


@app.post("/sessoes/{session_id}/mensagens")
async def enviar_mensagem(session_id: str, pedido: PedidoMensagem) -> dict[str, Any]:
    sessao = await _obter_sessao(session_id)
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    mensagem = types.Content(
        role="user",
        parts=[types.Part(text=pedido.texto)],
    )
    return await _executar(session_id, mensagem)


@app.post("/sessoes/{session_id}/confirmacoes")
async def responder_confirmacao(
    session_id: str, pedido: PedidoConfirmacao
) -> dict[str, Any]:
    sessao = await _obter_sessao(session_id)
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    pendentes = listar_pendentes(sessao.events)
    alvo = next((item for item in pendentes if item["id"] == pedido.id), None)
    if alvo is None:
        raise HTTPException(status_code=409, detail="Confirmação não está pendente.")
    mensagem = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=pedido.id,
                    name=REQUEST_CONFIRMATION_FUNCTION_CALL_NAME,
                    response={
                        "confirmed": pedido.confirmado,
                        "payload": alvo["payload"],
                    },
                )
            )
        ],
    )
    return await _executar(session_id, mensagem, invocation_id=alvo["invocation_id"])


@app.get("/sessoes/{session_id}/eventos")
async def listar_eventos(session_id: str) -> list[dict[str, Any]]:
    sessao = await _obter_sessao(session_id)
    if sessao is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return [
        evento.model_dump(mode="json", exclude_none=False) for evento in sessao.events
    ]


@app.get("/apartamentos/{apartamento}/reservas")
async def reservas_do_apartamento(apartamento: str) -> list[dict[str, str]]:
    return store.listar_reservas(apartamento)


@app.get("/apartamentos/{apartamento}/visitantes")
async def visitantes_do_apartamento(apartamento: str) -> list[dict[str, str]]:
    return store.listar_visitantes(apartamento)
