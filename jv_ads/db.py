"""Registro local de ações aplicadas (SQLite).

Toda alteração feita na conta pelo JV Ads fica registrada aqui,
com data, tipo, alvo e resultado — para auditoria e para reverter
manualmente se preciso.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "jv_ads.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS acoes_aplicadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            tipo TEXT NOT NULL,
            alvo TEXT NOT NULL,
            detalhes TEXT,
            resultado TEXT
        )
        """
    )
    return conn


def registrar_acao(tipo: str, alvo: str, detalhes: str, resultado: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO acoes_aplicadas (data_hora, tipo, alvo, detalhes, resultado) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), tipo, alvo, detalhes, resultado),
        )


def listar_acoes(limite: int = 50) -> list[tuple]:
    with _conn() as conn:
        cur = conn.execute(
            "SELECT data_hora, tipo, alvo, resultado FROM acoes_aplicadas "
            "ORDER BY id DESC LIMIT ?",
            (limite,),
        )
        return cur.fetchall()
