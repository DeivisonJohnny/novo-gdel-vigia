import { Body, Controller, Get, HttpCode, Post, Req, Res, UseGuards } from "@nestjs/common";
import { Request, Response } from "express";
import { SessaoGuard } from "../comum/guards/sessao.guard";
import { UsuarioAtual } from "../comum/decorators/usuario-atual.decorator";
import { UsuarioPublico } from "../comum/interfaces/usuario-publico.interface";
import { AutenticacaoService } from "./autenticacao.service";
import { LoginDto } from "./dto/login.dto";

@Controller("api/auth")
export class AutenticacaoController {
  constructor(private readonly autenticacao: AutenticacaoService) {}

  @Post("login")
  @HttpCode(200)
  entrar(@Body() dados: LoginDto, @Req() requisicao: Request, @Res({ passthrough: true }) resposta: Response) {
    return this.autenticacao.entrar(dados, requisicao, resposta);
  }

  @Post("logout")
  @HttpCode(200)
  async sair(@Req() requisicao: Request, @Res({ passthrough: true }) resposta: Response) {
    await this.autenticacao.sair(requisicao, resposta);
    return { ok: true };
  }

  @Get("eu")
  @UseGuards(SessaoGuard)
  eu(@UsuarioAtual() usuario: UsuarioPublico) {
    return usuario;
  }
}
