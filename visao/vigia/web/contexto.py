from dataclasses import dataclass
from datetime import datetime, time as hora, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request

from ..seguranca import hash_do_token

COOKIE_SESSAO = "vigia_sessao"
POR_PAGINA_MAXIMO = 200


@dataclass
class Contexto:
    cfg: dict
    banco: object
    notificador: object
    motor: object = None
    cadastro: object = None

    @property
    def fuso(self):
        return ZoneInfo(self.cfg["sistema"]["fuso"])

    def inicio_do_dia(self, dia=None):
        dia = dia or datetime.now(self.fuso).date()
        return datetime.combine(dia, hora.min, self.fuso).timestamp()

    def periodo(self, desde, ate):
        inicio = self.inicio_do_dia(datetime.fromisoformat(desde).date()) if desde else None
        fim = self.inicio_do_dia(datetime.fromisoformat(ate).date() + timedelta(days=1)) if ate else None
        return inicio, fim


def contexto(request: Request) -> Contexto:
    return request.app.state.contexto


def usuario_atual(request: Request, ctx: Contexto = Depends(contexto)):
    token = request.cookies.get(COOKIE_SESSAO)
    usuario = ctx.banco.usuario_da_sessao(hash_do_token(token)) if token else None
    if not usuario:
        raise HTTPException(401, "sessão expirada")
    return usuario


def exigir_admin(usuario=Depends(usuario_atual)):
    if usuario["papel"] != "admin":
        raise HTTPException(403, "apenas administradores")
    return usuario


def paginacao(pagina: int = 1, por_pagina: int = 25):
    por_pagina = max(1, min(por_pagina, POR_PAGINA_MAXIMO))
    return {"limite": por_pagina, "deslocamento": (max(pagina, 1) - 1) * por_pagina}


def analise_da_camera(ctx: Contexto, nome: str):
    if nome not in ctx.cfg["cameras"]:
        raise HTTPException(404, "câmera não encontrada")
    return ctx.motor.analises.get(nome) if ctx.motor else None
