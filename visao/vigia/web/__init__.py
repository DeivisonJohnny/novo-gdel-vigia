from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import RAIZ
from .contexto import Contexto
from .rotas import cameras, painel, registros, sistema

PASTA_FRONTEND = RAIZ.parent / "frontend" / "dist"

CABECALHOS_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}


def _servir_frontend(app: FastAPI, pasta: Path):
    if not (pasta / "index.html").exists():
        return

    app.mount("/assets", StaticFiles(directory=pasta / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        if caminho == "api" or caminho.startswith("api/"):
            raise HTTPException(404, "rota não encontrada")
        arquivo = (pasta / caminho).resolve()
        if caminho and arquivo.is_relative_to(pasta.resolve()) and arquivo.is_file():
            return FileResponse(arquivo)
        return FileResponse(pasta / "index.html", headers={"Cache-Control": "no-cache"})


def criar_app(ctx: Contexto, pasta_frontend: Path = PASTA_FRONTEND):
    app = FastAPI(title=ctx.cfg["sistema"]["nome"], version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.contexto = ctx

    @app.middleware("http")
    async def seguranca(request, chamar):
        resposta = await chamar(request)
        resposta.headers.update(CABECALHOS_SEGURANCA)
        return resposta

    for modulo in (painel, cameras, registros, sistema):
        app.include_router(modulo.rotas)
    _servir_frontend(app, pasta_frontend)
    return app
