"""Caminhos, nome da aplicação e modelo usado por todos os agentes."""

from pathlib import Path

def _encontrar_raiz() -> Path:
    aqui = Path(__file__).resolve()
    for candidato in aqui.parents:
        if (candidato / "dados" / "reservas.json").is_file():
            return candidato
    return aqui.parents[1]


RAIZ = _encontrar_raiz()
DADOS = RAIZ / "dados"
RUNTIME = RAIZ / "runtime"
BANCO_NEGOCIO = RUNTIME / "condominio.sqlite"
BANCO_SESSOES = RUNTIME / "sessoes.sqlite"

APP_NAME = "residencial_aurora"
MODELO = "gemini-2.5-flash"

# user_id fixo: o apartamento autenticado fica só no state da sessão.
USER_ID = "morador"
