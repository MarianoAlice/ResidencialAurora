"""Consulta `dados/regulamento.md` e devolve um único capítulo."""

from __future__ import annotations

import re
import unicodedata

from aurora.config import DADOS

_CAPITULOS: dict[str, str] | None = None

# A primeira regra que casar ganha. Termos mais específicos vêm antes.
_TEMAS = (
    (("piscina",), "IV"),
    (("brinquedoteca", "playground", "academia"), "V"),
    (("churrasqueira", "quadra", "salao"), "VI"),
    (("portaria", "visitante", "acesso", "seguranca"), "VII"),
    (("animal", "pet", "estimacao"), "VIII"),
    (("mudanca",), "IX"),
    (("reforma", "obra"), "X"),
    (("garagem", "veiculo", "vaga"), "XI"),
    (("reciclagem", "lixo"), "XII"),
    (("silencio", "barulho", "sossego"), "III"),
    (("infracao", "multa", "penalidade"), "XIII"),
    (("direito", "dever"), "II"),
)


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caractere
        for caractere in normalizado
        if unicodedata.category(caractere) != "Mn"
    )


def _capitulos() -> dict[str, str]:
    global _CAPITULOS
    if _CAPITULOS is None:
        texto = (DADOS / "regulamento.md").read_text(encoding="utf-8")
        partes = re.split(r"(?=^## Capítulo )", texto, flags=re.MULTILINE)
        encontrados: dict[str, str] = {}
        for parte in partes:
            titulo = re.match(r"^## Capítulo ([IVXLC]+)\b", parte)
            if titulo:
                encontrados[titulo.group(1)] = parte.strip()
        _CAPITULOS = encontrados
    return _CAPITULOS


def consultar_regulamento(tema: str) -> dict:
    """Devolve o capítulo do regulamento que responde ao tema.

    Args:
        tema: Assunto da dúvida, por exemplo piscina, academia ou mudança.

    Returns:
        Um único capítulo. Se o tema não casar, devolve aviso curto, sem o arquivo.
    """
    chave = _sem_acento(tema)
    numero = None
    for termos, capitulo in _TEMAS:
        if any(termo in chave for termo in termos):
            numero = capitulo
            break
    if numero is None:
        return {
            "encontrado": False,
            "mensagem": "Nenhum capítulo corresponde a esse tema.",
        }
    return {"encontrado": True, "capitulo": numero, "texto": _capitulos()[numero]}
