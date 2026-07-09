"""Registro local de ações aplicadas (SQLite).

Toda alteração feita na conta pelo JV Ads fica registrada aqui,
com data, tipo, alvo e resultado — para auditoria e para reverter
manualmente se preciso.
"""
import sqlite3
from datetime import datetime, timedelta
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recusas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            chave TEXT NOT NULL,
            titulo TEXT NOT NULL,
            motivo TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            desperdicios INTEGER,
            oportunidades INTEGER,
            economia_estimada REAL,
            maior_problema TEXT,
            melhor_campanha TEXT
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


# ------------------------------------------------- aprendizado com o usuário

def registrar_recusa(chave: str, titulo: str, motivo: str) -> None:
    """Guarda um 'não quero' do usuário e o motivo dele."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO recusas (data_hora, chave, titulo, motivo) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), chave, titulo, motivo),
        )


def recusas_recentes(dias: int = 30) -> dict:
    """Recusas dos últimos N dias: chave -> motivo (a mais recente vence)."""
    limite = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    with _conn() as conn:
        cur = conn.execute(
            "SELECT chave, motivo FROM recusas WHERE data_hora >= ? ORDER BY id",
            (limite,),
        )
        return {chave: (motivo or "sem motivo informado") for chave, motivo in cur}


# ------------------------------------------------------------ diário automático

def registrar_diario(desperdicios: int, oportunidades: int,
                     economia_estimada: float, maior_problema: str,
                     melhor_campanha: str) -> None:
    """Grava o resumo do dia. Uma análise nova no mesmo dia substitui a anterior."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    with _conn() as conn:
        conn.execute("DELETE FROM diario WHERE data = ?", (hoje,))
        conn.execute(
            "INSERT INTO diario (data, data_hora, desperdicios, oportunidades, "
            "economia_estimada, maior_problema, melhor_campanha) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hoje, datetime.now().isoformat(timespec="seconds"), desperdicios,
             oportunidades, economia_estimada, maior_problema, melhor_campanha),
        )


def listar_diario(limite: int = 60) -> list[tuple]:
    with _conn() as conn:
        cur = conn.execute(
            "SELECT data, desperdicios, oportunidades, economia_estimada, "
            "maior_problema, melhor_campanha FROM diario ORDER BY data DESC LIMIT ?",
            (limite,),
        )
        return cur.fetchall()
