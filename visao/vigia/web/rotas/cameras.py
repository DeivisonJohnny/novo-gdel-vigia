import asyncio
import json
from typing import Annotated

import httpx
import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from ...cadastro import CadastroInvalido
from ...config import nome_da_loja
from ...deteccao.marcacao import origem_da_marcacao
from ..contexto import Contexto, analise_da_camera, contexto, exigir_admin, usuario_atual

rotas = APIRouter(prefix="/api/cameras", tags=["câmeras"], dependencies=[Depends(usuario_atual)])

INTERVALO_DETECCOES_S = 0.15
DETECCAO_VELHA_S = 3
TIMEOUT_WHEP_S = 15
MAX_MAQUININHAS = 6
LADO_MINIMO_MAQUININHA = 0.01
CASAS_COORDENADA = 4

Coordenada = Annotated[float, Field(ge=0, le=1)]


def _url_webrtc(ctx: Contexto, nome: str, sufixo=""):
    base = (ctx.cfg["roteador"].get("webrtc") or "").rstrip("/")
    if not base:
        raise HTTPException(404, "WebRTC desligado neste ambiente")
    return f"{base}/{ctx.cfg['cameras'][nome]['caminho']}/whep{sufixo}"


def _com_loja(ctx: Contexto, camera):
    return {**camera, "loja_nome": nome_da_loja(ctx.cfg, camera.get("loja"))}


@rotas.get("")
def listar(ctx: Contexto = Depends(contexto)):
    cameras = ctx.motor.cameras() if ctx.motor else []
    return {"webrtc": bool(ctx.cfg["roteador"].get("webrtc")), "cameras": [_com_loja(ctx, c) for c in cameras]}


class NovaLoja(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    pdv: str = Field(default="", max_length=80, pattern=r"^[0-9, ]*$")


class NovaCamera(BaseModel):
    codigo: str = Field(min_length=3, max_length=40)
    descricao: str = Field(default="", max_length=120)
    loja: str | None = None
    nova_loja: NovaLoja | None = None


def _cadastro(ctx: Contexto):
    if not ctx.cadastro:
        raise HTTPException(503, "cadastro de câmeras desligado neste ambiente")
    return ctx.cadastro


@rotas.get("/cadastro", dependencies=[Depends(exigir_admin)])
def listar_cadastro(ctx: Contexto = Depends(contexto)):
    return _cadastro(ctx).listar()


@rotas.post("/cadastro", status_code=201, dependencies=[Depends(exigir_admin)])
def cadastrar(dados: NovaCamera, ctx: Contexto = Depends(contexto)):
    if not dados.loja and not dados.nova_loja:
        raise HTTPException(422, "escolha a loja ou informe uma nova")
    try:
        return _cadastro(ctx).criar(dados.codigo, dados.descricao, dados.loja,
                                    dados.nova_loja.model_dump() if dados.nova_loja else None)
    except CadastroInvalido as erro:
        raise HTTPException(409, str(erro))


class PdvDaLoja(BaseModel):
    pdv: str = Field(default="", max_length=80, pattern=r"^[0-9, ]*$")


class RecorteSemCompra(BaseModel):
    ativo: bool
    espera_min: int = Field(ge=1, le=60)


@rotas.get("/pdvs-touchpay", dependencies=[Depends(exigir_admin)])
def pdvs_touchpay(ctx: Contexto = Depends(contexto)):
    try:
        return _cadastro(ctx).pdvs_touchpay()
    except requests.RequestException as erro:
        raise HTTPException(502, f"TouchPay indisponível: {type(erro).__name__}")


@rotas.put("/lojas/{chave}/pdv", dependencies=[Depends(exigir_admin)])
def definir_pdv(chave: str, dados: PdvDaLoja, ctx: Contexto = Depends(contexto)):
    try:
        return _cadastro(ctx).definir_pdv(chave, dados.pdv)
    except CadastroInvalido as erro:
        raise HTTPException(404, str(erro))


@rotas.put("/lojas/{chave}/recorte-sem-compra")
def configurar_recorte_sem_compra(chave: str, dados: RecorteSemCompra, ctx: Contexto = Depends(contexto),
                                  admin=Depends(exigir_admin)):
    try:
        return _cadastro(ctx).configurar_recorte_sem_compra(chave, dados.ativo, dados.espera_min * 60, admin["email"])
    except CadastroInvalido as erro:
        raise HTTPException(404, str(erro))


@rotas.delete("/cadastro/{nome}", dependencies=[Depends(exigir_admin)])
def descadastrar(nome: str, ctx: Contexto = Depends(contexto)):
    try:
        return _cadastro(ctx).remover(nome)
    except CadastroInvalido as erro:
        raise HTTPException(404, str(erro))


@rotas.get("/deteccoes")
async def deteccoes(request: Request, cameras: str | None = None, ctx: Contexto = Depends(contexto)):
    nomes = [nome for nome in (cameras.split(",") if cameras else list(ctx.cfg["cameras"])) if nome in ctx.cfg["cameras"]]

    async def fluxo():
        ultimos = {}
        while not await request.is_disconnected():
            for nome in nomes:
                analise = ctx.motor.analises.get(nome) if ctx.motor else None
                atual = analise.deteccao if analise else None
                if atual and atual["t"] != ultimos.get(nome):
                    ultimos[nome] = atual["t"]
                    yield f"data: {json.dumps({'camera': nome, 'deteccao': atual})}\n\n"
            await asyncio.sleep(INTERVALO_DETECCOES_S)

    return StreamingResponse(fluxo(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class Maquininhas(BaseModel):
    caixas: list[tuple[Coordenada, Coordenada, Coordenada, Coordenada]] = Field(min_length=1, max_length=MAX_MAQUININHAS)

    @field_validator("caixas")
    @classmethod
    def caixas_com_area(cls, caixas):
        if any(x2 - x1 < LADO_MINIMO_MAQUININHA or y2 - y1 < LADO_MINIMO_MAQUININHA for x1, y1, x2, y2 in caixas):
            raise ValueError("cada maquininha precisa ter largura e altura")
        return caixas


def _marcacao(ctx: Contexto, nome: str):
    analise = analise_da_camera(ctx, nome)
    marcadas = ctx.banco.maquininhas_marcadas().get(nome)
    return {"camera": nome, "origem": origem_da_marcacao(marcadas, sem_marcacao="automatica"), "manual": marcadas or None,
            "automatica": analise.totem_norm if analise else None}


def _aplicar_marcacao(ctx: Contexto, nome: str, caixas, admin):
    ctx.banco.salvar_maquininhas(nome, caixas, admin["email"])
    if ctx.motor:
        ctx.motor.marcar_maquininhas(nome, caixas)
    return _marcacao(ctx, nome)


@rotas.get("/{nome}/maquininhas", dependencies=[Depends(exigir_admin)])
def consultar_maquininhas(nome: str, ctx: Contexto = Depends(contexto)):
    return _marcacao(ctx, nome)


@rotas.put("/{nome}/maquininhas")
def marcar_maquininhas(nome: str, dados: Maquininhas, ctx: Contexto = Depends(contexto), admin=Depends(exigir_admin)):
    analise_da_camera(ctx, nome)
    return _aplicar_marcacao(ctx, nome, [[round(v, CASAS_COORDENADA) for v in caixa] for caixa in dados.caixas], admin)


@rotas.put("/{nome}/maquininhas/ausente")
def marcar_sem_maquininha(nome: str, ctx: Contexto = Depends(contexto), admin=Depends(exigir_admin)):
    analise_da_camera(ctx, nome)
    return _aplicar_marcacao(ctx, nome, [], admin)


@rotas.delete("/{nome}/maquininhas", dependencies=[Depends(exigir_admin)])
def remover_maquininhas(nome: str, ctx: Contexto = Depends(contexto)):
    analise_da_camera(ctx, nome)
    ctx.banco.remover_maquininhas(nome)
    if ctx.motor:
        ctx.motor.marcar_maquininhas(nome, None)
    return _marcacao(ctx, nome)


@rotas.get("/{nome}/quadro")
async def quadro(nome: str, ctx: Contexto = Depends(contexto)):
    analise = analise_da_camera(ctx, nome)
    jpeg = await asyncio.to_thread(analise.jpeg_atual) if analise else None
    if not jpeg:
        raise HTTPException(503, "câmera ainda sem imagem")
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


async def _encaminhar(metodo, url, request: Request):
    corpo = await request.body()
    cabecalhos = {chave: valor for chave, valor in request.headers.items()
                  if chave.lower() in ("content-type", "if-match")}
    async with httpx.AsyncClient(timeout=TIMEOUT_WHEP_S) as cliente:
        try:
            return await cliente.request(metodo, url, content=corpo, headers=cabecalhos)
        except httpx.HTTPError as erro:
            raise HTTPException(502, f"roteador de vídeo indisponível: {type(erro).__name__}")


@rotas.post("/{nome}/whep")
async def iniciar_webrtc(nome: str, request: Request, ctx: Contexto = Depends(contexto)):
    resposta = await _encaminhar("POST", _url_webrtc(ctx, nome), request)
    cabecalhos = {"Content-Type": resposta.headers.get("content-type", "application/sdp")}
    sessao = resposta.headers.get("location", "").rstrip("/").rsplit("/", 1)[-1]
    if sessao:
        cabecalhos["Location"] = f"/api/cameras/{nome}/whep/{sessao}"
    if "etag" in resposta.headers:
        cabecalhos["ETag"] = resposta.headers["etag"]
    return Response(resposta.content, status_code=resposta.status_code, headers=cabecalhos)


@rotas.api_route("/{nome}/whep/{sessao}", methods=["PATCH", "DELETE"])
async def sessao_webrtc(nome: str, sessao: str, request: Request, ctx: Contexto = Depends(contexto)):
    resposta = await _encaminhar(request.method, _url_webrtc(ctx, nome, f"/{sessao}"), request)
    return Response(resposta.content, status_code=resposta.status_code,
                    headers={"Content-Type": resposta.headers.get("content-type", "application/trickle-ice-sdpfrag")})
