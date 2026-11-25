import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from ... import __version__
from ..contexto import Contexto, contexto, exigir_admin, usuario_atual

rotas = APIRouter(prefix="/api", tags=["sistema"])

PING_EVENTOS_S = 20
TIPOS_DE_ARQUIVO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}


@rotas.get("/sistema", dependencies=[Depends(exigir_admin)])
def sistema(ctx: Contexto = Depends(contexto)):
    return {
        "versao": __version__,
        "ambiente": ctx.cfg["ambiente"],
        "nome": ctx.cfg["sistema"]["nome"],
        "motor": ctx.motor.status() if ctx.motor else {"situacao": "desligado"},
        "cameras": ctx.motor.cameras() if ctx.motor else [],
    }


@rotas.get("/config-publica")
def config_publica(ctx: Contexto = Depends(contexto)):
    return {"nome": ctx.cfg["sistema"]["nome"], "versao": __version__, "ambiente": ctx.cfg["ambiente"]}


@rotas.get("/eventos", dependencies=[Depends(usuario_atual)])
async def eventos(request: Request, ctx: Contexto = Depends(contexto)):
    ultimo_id = int(request.headers.get("last-event-id") or 0)
    assinatura = ctx.notificador.assinar()
    _, fila = assinatura

    def formatar(mensagem):
        return f"id: {mensagem['id']}\nevent: {mensagem['tipo']}\ndata: {json.dumps(mensagem, ensure_ascii=False)}\n\n"

    async def fluxo():
        try:
            yield ": conectado\n\n"
            for mensagem in ctx.notificador.depois_de(ultimo_id) if ultimo_id else []:
                yield formatar(mensagem)
            while not await request.is_disconnected():
                try:
                    yield formatar(await asyncio.wait_for(fila.get(), PING_EVENTOS_S))
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            ctx.notificador.cancelar(assinatura)

    return StreamingResponse(fluxo(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@rotas.get("/arquivos/{caminho:path}", dependencies=[Depends(usuario_atual)])
def arquivo(caminho: str, ctx: Contexto = Depends(contexto)):
    raiz = Path(ctx.cfg["dados"]["evidencias"]).resolve()
    alvo = (raiz / caminho).resolve()
    if not alvo.is_relative_to(raiz) or not alvo.is_file() or alvo.suffix.lower() not in TIPOS_DE_ARQUIVO:
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(alvo, media_type=TIPOS_DE_ARQUIVO[alvo.suffix.lower()], headers={"Cache-Control": "private, max-age=86400"})
