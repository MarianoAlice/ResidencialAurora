"""Store de negócio em SQLite.

Reservas, visitantes e códigos usados ficam aqui. `dados/` só é lido.
A exclusividade de área e data vale no insert, dentro de uma transação
com `BEGIN IMMEDIATE` e do índice único parcial `ux_ocupacao_ativa`.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from typing import Any

from aurora.config import BANCO_NEGOCIO, DADOS, RUNTIME

_FRAGMENTOS_PROIBIDOS = ("RSV", "1377", "4821", "2950", "302")


def conectar() -> sqlite3.Connection:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(BANCO_NEGOCIO, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def criar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reservas (
            codigo TEXT PRIMARY KEY,
            apartamento TEXT NOT NULL,
            area TEXT NOT NULL,
            data TEXT NOT NULL,
            ativa INTEGER NOT NULL CHECK (ativa IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS codigos_usados (
            codigo TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS visitantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartamento TEXT NOT NULL,
            nome TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_ocupacao_ativa
            ON reservas(area, data) WHERE ativa = 1;
        """
    )


def _semear(conn: sqlite3.Connection) -> None:
    reservas = json.loads((DADOS / "reservas.json").read_text(encoding="utf-8"))
    visitantes = json.loads((DADOS / "visitantes.json").read_text(encoding="utf-8"))
    for reserva in reservas:
        conn.execute(
            "INSERT INTO codigos_usados(codigo) VALUES (?)",
            (reserva["codigo"],),
        )
        conn.execute(
            """
            INSERT INTO reservas(codigo, apartamento, area, data, ativa)
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                reserva["codigo"],
                reserva["apartamento"],
                reserva["area"],
                reserva["data"],
            ),
        )
    for visitante in visitantes:
        conn.execute(
            "INSERT INTO visitantes(apartamento, nome, data) VALUES (?, ?, ?)",
            (visitante["apartamento"], visitante["nome"], visitante["data"]),
        )


def _commit_ou_desfaz(conn: sqlite3.Connection, acao) -> Any:
    conn.execute("BEGIN IMMEDIATE")
    try:
        resultado = acao()
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
        return resultado


def garantir_carregado() -> None:
    """Cria o banco e, se ainda não houve carga, copia `dados/`."""
    conn = conectar()
    try:
        criar_schema(conn)
        row = conn.execute(
            "SELECT valor FROM meta WHERE chave = 'carregado'"
        ).fetchone()
        if row is not None:
            return

        def carregar() -> None:
            _semear(conn)
            conn.execute(
                "INSERT INTO meta(chave, valor) VALUES ('carregado', '1')"
            )

        _commit_ou_desfaz(conn, carregar)
    finally:
        conn.close()


def restaurar() -> None:
    """Regrava reservas, visitantes e códigos a partir de `dados/`.

    Não apaga sessões do ADK.
    """
    conn = conectar()
    try:
        criar_schema(conn)

        def repor() -> None:
            conn.execute("DELETE FROM reservas")
            conn.execute("DELETE FROM visitantes")
            conn.execute("DELETE FROM codigos_usados")
            _semear(conn)
            conn.execute(
                """
                INSERT INTO meta(chave, valor) VALUES ('carregado', '1')
                ON CONFLICT(chave) DO UPDATE SET valor = '1'
                """
            )

        _commit_ou_desfaz(conn, repor)
    finally:
        conn.close()


def listar_reservas(apartamento: str) -> list[dict[str, str]]:
    conn = conectar()
    try:
        rows = conn.execute(
            """
            SELECT codigo, area, data
            FROM reservas
            WHERE apartamento = ? AND ativa = 1
            ORDER BY data, codigo
            """,
            (apartamento,),
        ).fetchall()
        return [
            {"codigo": row["codigo"], "area": row["area"], "data": row["data"]}
            for row in rows
        ]
    finally:
        conn.close()


def listar_visitantes(apartamento: str) -> list[dict[str, str]]:
    conn = conectar()
    try:
        rows = conn.execute(
            """
            SELECT nome, data
            FROM visitantes
            WHERE apartamento = ?
            ORDER BY data, nome, id
            """,
            (apartamento,),
        ).fetchall()
        return [{"nome": row["nome"], "data": row["data"]} for row in rows]
    finally:
        conn.close()


def data_ocupada(area: str, data: str) -> bool:
    """Diz só se existe reserva ativa. Não devolve dono nem código."""
    conn = conectar()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM reservas
            WHERE area = ? AND data = ? AND ativa = 1
            """,
            (area, data),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _novo_codigo(conn: sqlite3.Connection) -> str:
    for _ in range(30):
        codigo = "AUR-" + secrets.token_hex(4).upper()
        if any(fragmento in codigo for fragmento in _FRAGMENTOS_PROIBIDOS):
            continue
        usado = conn.execute(
            "SELECT 1 FROM codigos_usados WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        if usado is None:
            return codigo
    raise RuntimeError("Não foi possível gerar um código de reserva.")


def reservar(apartamento: str, area: str, data: str) -> dict[str, Any]:
    """Grava uma reserva ativa ou recusa se a data já foi ocupada.

    A leitura e o insert acontecem na mesma transação de escrita.
    Se outra transação gravar primeiro, o índice único falha o segundo insert.
    """
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            propria = conn.execute(
                """
                SELECT codigo FROM reservas
                WHERE apartamento = ? AND area = ? AND data = ? AND ativa = 1
                """,
                (apartamento, area, data),
            ).fetchone()
            if propria is not None:
                conn.execute("COMMIT")
                return {"ok": True, "codigo": propria["codigo"]}

            codigo = _novo_codigo(conn)
            conn.execute(
                "INSERT INTO codigos_usados(codigo) VALUES (?)",
                (codigo,),
            )
            conn.execute(
                """
                INSERT INTO reservas(codigo, apartamento, area, data, ativa)
                VALUES (?, ?, ?, ?, 1)
                """,
                (codigo, apartamento, area, data),
            )
            conn.execute("COMMIT")
            return {"ok": True, "codigo": codigo}
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return {"ok": False, "motivo": "ocupada"}
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def cancelar(apartamento: str, area: str, data: str) -> dict[str, Any]:
    """Cancela só se a reserva ativa for do apartamento informado.

    A busca já filtra pelo apartamento, então o retorno não traz reserva alheia.
    O código permanece em `codigos_usados`.
    """
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """
                SELECT codigo, area, data FROM reservas
                WHERE apartamento = ? AND area = ? AND data = ? AND ativa = 1
                """,
                (apartamento, area, data),
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return {"ok": False}
            conn.execute(
                "UPDATE reservas SET ativa = 0 WHERE codigo = ? AND apartamento = ?",
                (row["codigo"], apartamento),
            )
            conn.execute("COMMIT")
            return {
                "ok": True,
                "codigo": row["codigo"],
                "area": row["area"],
                "data": row["data"],
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def autorizar_visitante(apartamento: str, nome: str, data: str) -> None:
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            existe = conn.execute(
                """
                SELECT 1 FROM visitantes
                WHERE apartamento = ? AND nome = ? AND data = ?
                """,
                (apartamento, nome, data),
            ).fetchone()
            if existe is None:
                conn.execute(
                    """
                    INSERT INTO visitantes(apartamento, nome, data)
                    VALUES (?, ?, ?)
                    """,
                    (apartamento, nome, data),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
