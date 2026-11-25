from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...config import nome_da_loja
from ...linha_do_tempo import linha_do_tempo
from ..contexto import Contexto, contexto, paginacao, usuario_atual

rotas = APIRouter(prefix="/api", tags=["registros"], dependencies=[Depends(usuario_atual)])


class Revisao(BaseModel):
    veredito: Literal["furto", "falso_positivo", "duvida"]
    observacao: str = Field(default="", max_length=2000)


def _nomear_loja(ctx: Contexto, registro):
    registro["loja_nome"] = nome_da_loja(ctx.cfg, registro.get("loja"))
    return registro


@rotas.get("/ocorrencias")
def listar_ocorrencias(situacao: str | None = None, nivel: str | None = None, loja: str | None = None,
                       desde: str | None = None, ate: str | None = None, tipo: str | None = None,
                       pagina=Depends(paginacao), ctx: Contexto = Depends(contexto)):
    inicio, fim = ctx.periodo(desde, ate)
    resultado = ctx.banco.listar_ocorrencias(situacao, nivel, loja, inicio, fim, tipo=tipo, **pagina)
    resultado["itens"] = [_nomear_loja(ctx, item) for item in resultado["itens"]]
    resultado["abertas"] = ctx.banco.contar_ocorrencias_abertas()
    return resultado


@rotas.get("/ocorrencias/{ocorrencia_id}")
def detalhar_ocorrencia(ocorrencia_id: int, ctx: Contexto = Depends(contexto)):
    ocorrencia = ctx.banco.ocorrencia(ocorrencia_id)
    if not ocorrencia:
        raise HTTPException(404, "ocorrência não encontrada")
    visita = ctx.banco.visita(ocorrencia["visita_id"]) or {}
    pagamento_id = ctx.banco.pagamento_da_visita(ocorrencia["visita_id"])
    pagamentos = ctx.banco.pagamentos_entre(ocorrencia["inicio"] - 300, ocorrencia["fim"] + 300)
    return {
        **_nomear_loja(ctx, ocorrencia),
        "pegadas": visita.get("pegadas"),
        "foi_totem": visita.get("foi_totem"),
        "linha_do_tempo": linha_do_tempo(visita),
        "pagamento": next((p for p in pagamentos if p["id"] == pagamento_id), None),
        "vendas_proximas": [p for p in pagamentos if p["loja"] == ocorrencia["loja"]],
    }


@rotas.post("/ocorrencias/{ocorrencia_id}/revisao")
def revisar_ocorrencia(ocorrencia_id: int, revisao: Revisao, usuario=Depends(usuario_atual), ctx: Contexto = Depends(contexto)):
    if not ctx.banco.ocorrencia(ocorrencia_id):
        raise HTTPException(404, "ocorrência não encontrada")
    ctx.banco.revisar_ocorrencia(ocorrencia_id, revisao.veredito, revisao.observacao.strip(), usuario["nome"])
    ctx.notificador.publicar("ocorrencia_revisada", {"id": ocorrencia_id, "veredito": revisao.veredito})
    return detalhar_ocorrencia(ocorrencia_id, ctx)


@rotas.get("/visitas")
def listar_visitas(resultado: str | None = None, loja: str | None = None, desde: str | None = None,
                   ate: str | None = None, pagina=Depends(paginacao), ctx: Contexto = Depends(contexto)):
    inicio, fim = ctx.periodo(desde, ate)
    dados = ctx.banco.listar_visitas(loja, resultado, inicio, fim, **pagina)
    dados["itens"] = [_nomear_loja(ctx, item) for item in dados["itens"]]
    return dados


@rotas.get("/vendas")
def listar_vendas(loja: str | None = None, desde: str | None = None, ate: str | None = None,
                  pagina=Depends(paginacao), ctx: Contexto = Depends(contexto)):
    inicio, fim = ctx.periodo(desde, ate)
    dados = ctx.banco.listar_pagamentos(loja, inicio, fim, **pagina)
    dados["itens"] = [_nomear_loja(ctx, item) for item in dados["itens"]]
    return dados
