import json
import logging
import sqlite3
import tempfile
from pathlib import Path

import psycopg

log = logging.getLogger(__name__)

ORDEM_DAS_TABELAS = ("usuarios", "sessoes", "lojas_cadastradas", "cameras_cadastradas", "maquininhas_marcadas",
                     "recorte_sem_compra", "pagamentos", "movimentacoes", "visitas", "ocorrencias")
CHAVES = {"usuarios": "id", "sessoes": "token", "lojas_cadastradas": "chave", "cameras_cadastradas": "nome",
          "maquininhas_marcadas": "camera", "recorte_sem_compra": "loja", "pagamentos": "id", "movimentacoes": "id",
          "visitas": "id", "ocorrencias": "id"}
COLUNAS_JSON = {"pagamentos": {"itens"}, "visitas": {"cameras", "dados"}, "maquininhas_marcadas": {"caixas"},
                "ocorrencias": {"cameras", "motivos", "evidencias", "clipes", "ia"}}
COLUNAS_LOGICAS = {"usuarios": {"ativo"}, "recorte_sem_compra": {"ativo"}, "movimentacoes": {"humana"}, "visitas": {"foi_totem"}}
TABELAS_COM_SEQUENCIA = ("usuarios", "ocorrencias")


class MigracaoRecusada(RuntimeError):
    pass


def _copia_consistente(origem, pasta):
    destino = Path(pasta) / "copia.db"
    with sqlite3.connect(f"file:{origem}?mode=ro", uri=True) as fonte, sqlite3.connect(destino) as copia:
        fonte.backup(copia)
    return destino


def _tabelas_do_sqlite(con):
    return {linha[0] for linha in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _colunas_do_postgres(pg, tabela):
    return [linha[0] for linha in pg.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (tabela,))]


def _converter(tabela, coluna, valor):
    if valor is None:
        return None
    if coluna in COLUNAS_JSON.get(tabela, ()):
        if valor == "":
            return None
        json.loads(valor)
        return valor
    if coluna in COLUNAS_LOGICAS.get(tabela, ()):
        return bool(valor)
    return valor


def _linhas(con, tabela, colunas):
    lista = ", ".join(f'"{c}"' for c in colunas)
    for linha in con.execute(f"SELECT {lista} FROM {tabela}"):
        yield tuple(_converter(tabela, coluna, valor) for coluna, valor in zip(colunas, linha))


def _contar_destino(pg):
    return {tabela: pg.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] for tabela in ORDEM_DAS_TABELAS}


def _chaves(fonte, tabela):
    return {str(linha[0]) for linha in fonte}


def migrar(arquivo_sqlite, url, substituir=False, simular=False):
    arquivo_sqlite = Path(arquivo_sqlite)
    if not arquivo_sqlite.is_file():
        raise MigracaoRecusada(f"arquivo SQLite não encontrado: {arquivo_sqlite}")
    with tempfile.TemporaryDirectory() as pasta, psycopg.connect(url) as pg:
        sqlite = sqlite3.connect(_copia_consistente(arquivo_sqlite, pasta))
        existentes = _tabelas_do_sqlite(sqlite)
        faltando_no_postgres = [t for t in ORDEM_DAS_TABELAS if not _colunas_do_postgres(pg, t)]
        if faltando_no_postgres:
            raise MigracaoRecusada(f"tabelas ausentes no Postgres: {', '.join(faltando_no_postgres)}. "
                                   "Rode antes as migrações do Prisma (npx prisma migrate deploy no backend)")
        ocupadas = {t: n for t, n in _contar_destino(pg).items() if n}
        if ocupadas and not substituir:
            raise MigracaoRecusada(f"o Postgres já tem dados ({ocupadas}). Use --substituir para apagar e copiar de novo")
        relatorio = []
        with pg.transaction():
            if ocupadas:
                pg.execute(f"TRUNCATE {', '.join(ORDEM_DAS_TABELAS)} RESTART IDENTITY")
            for tabela in ORDEM_DAS_TABELAS:
                if tabela not in existentes:
                    relatorio.append((tabela, 0, 0, "não existe no SQLite (versão antiga): fica vazia"))
                    continue
                colunas_sqlite = [linha[1] for linha in sqlite.execute(f"PRAGMA table_info({tabela})")]
                colunas = [c for c in colunas_sqlite if c in set(_colunas_do_postgres(pg, tabela))]
                linhas = list(_linhas(sqlite, tabela, colunas))
                if linhas:
                    marcadores = ", ".join(["%s"] * len(colunas))
                    lista = ", ".join(f'"{c}"' for c in colunas)
                    with pg.cursor() as cursor:
                        cursor.executemany(f"INSERT INTO {tabela} ({lista}) VALUES ({marcadores})", linhas)
                chave = CHAVES[tabela]
                origem = _chaves(sqlite.execute(f"SELECT {chave} FROM {tabela}"), tabela)
                destino = _chaves(pg.execute(f"SELECT {chave} FROM {tabela}"), tabela)
                if origem != destino:
                    raise MigracaoRecusada(f"{tabela}: {len(origem - destino)} linha(s) não chegaram ao Postgres")
                relatorio.append((tabela, len(origem), len(destino), "ok"))
            for tabela in TABELAS_COM_SEQUENCIA:
                pg.execute(f"SELECT setval(pg_get_serial_sequence('{tabela}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {tabela}")
            if simular:
                raise _Simulacao(relatorio)
        sqlite.close()
        return relatorio


class _Simulacao(Exception):
    def __init__(self, relatorio):
        super().__init__("simulação")
        self.relatorio = relatorio


def executar(arquivo_sqlite, url, substituir=False, simular=False):
    try:
        return migrar(arquivo_sqlite, url, substituir, simular), False
    except _Simulacao as simulacao:
        return simulacao.relatorio, True
