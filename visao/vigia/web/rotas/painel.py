from datetime import datetime

from fastapi import APIRouter, Depends

from ...config import nome_da_loja
from ..contexto import Contexto, contexto, usuario_atual

rotas = APIRouter(prefix="/api", tags=["painel"], dependencies=[Depends(usuario_atual)])

OCORRENCIAS_RECENTES = 6


@rotas.get("/lojas")
def lojas(ctx: Contexto = Depends(contexto)):
    return [{"id": chave, "nome": loja.get("nome") or chave, "pdv_configurado": bool(str(loja.get("pdv") or "").strip()),
             "cameras": [nome for nome, c in ctx.cfg["cameras"].items() if c.get("loja") == chave]}
            for chave, loja in (ctx.cfg.get("lojas") or {}).items()]


@rotas.get("/painel")
def painel(loja: str | None = None, ctx: Contexto = Depends(contexto)):
    inicio_do_dia = ctx.inicio_do_dia()
    deslocamento = int(datetime.now(ctx.fuso).utcoffset().total_seconds())
    recentes = ctx.banco.listar_ocorrencias(loja=loja, limite=OCORRENCIAS_RECENTES)["itens"]
    cameras = ctx.motor.cameras() if ctx.motor else []
    return {
        "hoje": ctx.banco.resumo(inicio_do_dia, loja),
        "por_hora": ctx.banco.movimento_por_hora(inicio_do_dia, deslocamento, loja),
        "ocorrencias_recentes": [{**o, "loja_nome": nome_da_loja(ctx.cfg, o.get("loja"))} for o in recentes],
        "cameras": [{**c, "loja_nome": nome_da_loja(ctx.cfg, c.get("loja"))}
                    for c in cameras if not loja or c.get("loja") == loja],
        "motor": ctx.motor.situacao if ctx.motor else "desligado",
    }
