# Residencial Aurora

Assistente do condomínio em Google ADK, exposto por uma API em `http://localhost:8000`. O modelo conduz a conversa. As regras de cobrança, acesso, apartamento, persistência, regulamento e unicidade da reserva ficam no código.

O modelo de todos os agentes é `gemini-2.5-flash`.

## Arquitetura

O morador fala com o agente principal `assistente_aurora`. Ele não lê nem grava o condomínio: só transfere o turno para um especialista. A divisão separa três políticas que não podem se misturar. Reserva cobra só quando a taxa é maior que zero. Visitante sempre pede confirmação. O regulamento é um texto longo que não pode entrar na instrução do principal.

| Agente | Responsabilidade | Como é acionado |
| --- | --- | --- |
| `assistente_aurora` | Entende o pedido e transfere | É o agente raiz da `App` |
| `especialista_reservas` | Lista, consulta disponibilidade, cancela e reserva | Transferência do principal |
| `especialista_visitantes` | Lista visitantes e autoriza entrada | Transferência do principal |
| `especialista_regulamento` | Responde dúvida de norma com um capítulo | Transferência do principal |

As tools que leem e gravam o condomínio estão em `aurora/tools_reservas.py` e `aurora/tools_visitantes.py`. A consulta ao regulamento está em `aurora/tools_regulamento.py`. O armazenamento de runtime está em `aurora/store.py` (SQLite local `runtime/condominio.sqlite`). A sessão do ADK fica em outro SQLite, `runtime/sessoes.sqlite`.

O apartamento autenticado é gravado uma vez, em `POST /sessoes`, no state da sessão (`state["apartamento"]`). As tools leem esse valor. Não existe parâmetro de apartamento.

Salão e churrasqueira, e toda autorização de visitante, chamam `request_confirmation`. A API devolve o id da function call `adk_request_confirmation`. `POST /sessoes/{id}/confirmacoes` só retoma esse id se ele ainda estiver pendente na sessão, reenviando a function response ao Runner com o `invocation_id` da execução pausada. A `App` está com `ResumabilityConfig(is_resumable=True)` para essa pausa sobreviver ao processo.

Não há serviço externo. Os dois bancos são arquivos locais.

## Garantias

### 1. Cobrança ou acesso só com confirmação

Em `aurora/tools_reservas.py`, `reservar_area` lê a taxa em `dados/areas.json` e chama `tool_context.request_confirmation` só quando a taxa é maior que zero. Quadra (taxa 0) grava direto. Cancelar não chama confirmação.

Em `aurora/tools_visitantes.py`, `autorizar_visitante` chama `request_confirmation` em toda entrada. A gravação acontece no ramo em que `tool_confirmation.confirmed` é verdadeiro. O texto da mensagem não entra nessa decisão.

Em `aurora/api.py`, `responder_confirmacao` procura o id nas pendências da sessão. Se o id não está pendente, inclusive se já foi respondido, responde 409 e não chama o Runner.

### 2. Cada sessão pertence a um apartamento

`criar_sessao`, em `aurora/api.py`, grava `state["apartamento"]` na criação. `_apartamento`, em `aurora/tools_reservas.py` e `aurora/tools_visitantes.py`, lê só esse state. As assinaturas das tools não têm parâmetro de apartamento, e nenhuma tool escreve essa chave.

`cancelar`, em `aurora/store.py`, filtra `apartamento = ?` antes de devolver qualquer campo. `consultar_disponibilidade` devolve apenas `livre` ou `ocupada`.

### 3. Nada se perde no reinício

`aurora/api.py` sobe `DatabaseSessionService` com SQLite (`sqlite+aiosqlite` em `runtime/sessoes.sqlite`). Reservas e visitantes ficam em `runtime/condominio.sqlite`. Reiniciar o processo não regrava `dados/` se o banco já foi carregado. O comando de restauração é outro.

### 4. O regulamento é consultado, não carregado

`consultar_regulamento`, em `aurora/tools_regulamento.py`, lê `dados/regulamento.md` e devolve um único capítulo. A instrução de `assistente_aurora`, em `aurora/agentes.py`, não contém o regulamento. O especialista responde só com o que a tool trouxe.

### 5. Dois moradores, uma reserva

`criar_schema`, em `aurora/store.py`, cria o índice único parcial `ux_ocupacao_ativa` em `(area, data)` onde `ativa = 1`. `reservar` abre a transação com `BEGIN IMMEDIATE` e faz o insert nessa transação. Se a segunda escrita perde a vaga, `IntegrityError` vira recusa de negócio (`Essa data acabou de ser ocupada.`), sem dono e sem código alheio, e a API continua em 200.

O código novo é gerado na mesma transação e registrado em `codigos_usados`. Cancelar desliga `ativa` e deixa o código nessa tabela.

## Como rodar

Pré-requisitos: Python 3.12 ou superior, [uv](https://docs.astral.sh/uv/) e uma chave do Google AI Studio.

Variáveis de `.env`, com os mesmos nomes de `.env.example`:

- `GOOGLE_API_KEY`: chave do Google AI Studio.
- `GOOGLE_GENAI_USE_VERTEXAI`: deixe `FALSE` para usar o AI Studio, não o Vertex.

Não há serviço externo para subir. O SQLite é arquivo local, criado na primeira execução.

```powershell
copy .env.example .env
uv sync
uv run aurora-restaurar
uv run aurora-api
```

A API escuta em `http://localhost:8000`.

`uv run aurora-restaurar` repõe reservas, visitantes e códigos usados a partir de `dados/`. Não apaga as sessões. `uv run aurora-api` sobe a API. Se o banco de negócio ainda não existir, a subida também faz a carga inicial. Reiniciar a API sem rodar a restauração conserva conversas, reservas, cancelamentos e visitantes.
