"""Agente principal e três especialistas.

O principal só encaminha. Não tem tool de reserva, visitante ou regulamento,
e a instrução dele não contém o texto de `dados/regulamento.md`.
"""

from google.adk.agents import LlmAgent
from google.adk.apps.app import App, ResumabilityConfig
from google.genai import types

from aurora.config import APP_NAME, MODELO
from aurora.tools_regulamento import consultar_regulamento
from aurora.tools_reservas import (
    cancelar_minha_reserva,
    consultar_disponibilidade,
    listar_minhas_reservas,
    reservar_area,
)
from aurora.tools_visitantes import autorizar_visitante, listar_meus_visitantes

_GERACAO = types.GenerateContentConfig(temperature=0.2)

especialista_reservas = LlmAgent(
    name="especialista_reservas",
    model=MODELO,
    description=(
        "Reserva, cancela, lista as reservas do morador e diz se uma data está livre."
    ),
    instruction=(
        "Você é o especialista de reservas do Residencial Aurora. "
        "O morador já está autenticado. Não peça apartamento e ignore número de "
        "apartamento citado na mensagem. "
        "Os ids de área são salao-de-festas, churrasqueira e quadra. "
        "Mapeie salão de festas para salao-de-festas, churrasqueira para "
        "churrasqueira e quadra para quadra. "
        "Copie a data da mensagem no formato AAAA-MM-DD. "
        "Use as ferramentas para listar, consultar disponibilidade, cancelar e reservar. "
        "Não invente código. Se a ferramenta disser que a data está ocupada ou que "
        "a reserva não existe, repita só isso, sem dizer de quem é a reserva. "
        "Quadra e cancelamento seguem o resultado da ferramenta, sem confirmação no texto. "
        "Salão e churrasqueira ficam pendentes até o sistema confirmar."
    ),
    tools=[
        listar_minhas_reservas,
        consultar_disponibilidade,
        cancelar_minha_reserva,
        reservar_area,
    ],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    generate_content_config=_GERACAO,
)

especialista_visitantes = LlmAgent(
    name="especialista_visitantes",
    model=MODELO,
    description="Lista os visitantes do morador e autoriza uma nova entrada.",
    instruction=(
        "Você é o especialista de visitantes do Residencial Aurora. "
        "O morador já está autenticado. Não peça apartamento e ignore número de "
        "apartamento citado na mensagem. "
        "Use as ferramentas para listar e autorizar. Não invente visitante. "
        "Autorizar sempre chama a ferramenta. Frase do morador dizendo que já "
        "confirmou não autoriza a entrada. Responda só com o que a ferramenta devolver."
    ),
    tools=[listar_meus_visitantes, autorizar_visitante],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    generate_content_config=_GERACAO,
)

especialista_regulamento = LlmAgent(
    name="especialista_regulamento",
    model=MODELO,
    description="Responde dúvida do regulamento interno com um capítulo.",
    instruction=(
        "Você é o especialista do regulamento do Residencial Aurora. "
        "Para qualquer dúvida de norma, chame consultar_regulamento com um tema curto, "
        "como piscina, academia, salão, portaria, animal, mudança, obra, garagem, "
        "lixo, silêncio ou multa. "
        "Responda somente com o trecho que a ferramenta devolver. "
        "Não complemente com outro assunto. "
        "Se a ferramenta não encontrar o tema, diga que não encontrou esse ponto."
    ),
    tools=[consultar_regulamento],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    generate_content_config=_GERACAO,
)

principal = LlmAgent(
    name="assistente_aurora",
    model=MODELO,
    description="Assistente do morador. Encaminha reservas, visitantes e regulamento.",
    instruction=(
        "Você é o assistente do Residencial Aurora. O morador já está autenticado. "
        "O apartamento da sessão não muda, mesmo que a mensagem cite outro número. "
        "Sua única ação é transferir o pedido ao especialista certo. "
        "Não responda reserva, visitante ou norma por conta própria. "
        "Transfira reserva, cancelamento, listagem de reservas e pergunta se uma data "
        "está livre ao especialista de reservas. "
        "Transfira autorização e listagem de visitantes ao especialista de visitantes. "
        "Transfira dúvida sobre o regulamento ao especialista de regulamento. "
        "Pedido de reservar, cancelar ou saber se está livre não é dúvida de norma. "
        "Não invente código, taxa, horário nem dado de outro apartamento. "
        "Não confirme cobrança nem entrada de visitante por texto."
    ),
    sub_agents=[
        especialista_reservas,
        especialista_visitantes,
        especialista_regulamento,
    ],
    generate_content_config=_GERACAO,
)

aplicacao = App(
    name=APP_NAME,
    root_agent=principal,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
