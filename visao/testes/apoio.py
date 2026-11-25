import os

from vigia.banco import Banco

TABELAS = ("sessoes", "usuarios", "pagamentos", "movimentacoes", "visitas", "ocorrencias",
          "lojas_cadastradas", "cameras_cadastradas", "maquininhas_marcadas", "recorte_sem_compra")

URL_PADRAO = "postgresql://vigia:vigia@127.0.0.1:5544/vigia"


def url_do_banco_de_teste():
    return os.environ.get("VIGIA_DATABASE_URL_TESTE") or os.environ.get("DATABASE_URL") or URL_PADRAO


def banco_de_teste():
    banco = Banco(url_do_banco_de_teste())
    limpar(banco)
    return banco


def limpar(banco):
    banco._exec(f"TRUNCATE {', '.join(TABELAS)} RESTART IDENTITY CASCADE")
