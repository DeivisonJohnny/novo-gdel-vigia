import { HttpException, HttpStatus, Injectable, UnauthorizedException } from "@nestjs/common";
import { Request, Response } from "express";
import { carregarConfiguracao } from "../configuracao";
import { PrismaService } from "../prisma/prisma.service";
import { LimiteDeTentativasService } from "../seguranca/limite-de-tentativas.service";
import { SegurancaService } from "../seguranca/seguranca.service";
import { COOKIE_SESSAO, UsuarioPublico } from "../comum/interfaces/usuario-publico.interface";
import { LoginDto } from "./dto/login.dto";

@Injectable()
export class AutenticacaoService {
  private readonly configuracao = carregarConfiguracao();

  constructor(
    private readonly prisma: PrismaService,
    private readonly seguranca: SegurancaService,
    private readonly limiteDeTentativas: LimiteDeTentativasService,
  ) {}

  async entrar(dados: LoginDto, requisicao: Request, resposta: Response): Promise<UsuarioPublico> {
    const email = dados.email.trim().toLowerCase();
    const chave = `${requisicao.ip ?? "-"}:${email}`;
    if (this.limiteDeTentativas.bloqueado(chave)) {
      throw new HttpException("muitas tentativas: aguarde alguns minutos", HttpStatus.TOO_MANY_REQUESTS);
    }
    const usuario = await this.prisma.usuario.findUnique({ where: { email } });
    if (!usuario || !usuario.ativo || !this.seguranca.conferirSenha(dados.senha, usuario.senha)) {
      this.limiteDeTentativas.falhou(chave);
      throw new UnauthorizedException("e-mail ou senha inválidos");
    }
    this.limiteDeTentativas.liberar(chave);

    const duracaoS = this.configuracao.sessaoHoras * 3600;
    const token = this.seguranca.novoToken();
    const agora = Date.now() / 1000;
    await this.prisma.sessao.create({
      data: {
        token: this.seguranca.hashDoToken(token),
        usuarioId: usuario.id,
        criadaEm: agora,
        expiraEm: agora + duracaoS,
      },
    });
    resposta.cookie(COOKIE_SESSAO, token, {
      maxAge: duracaoS * 1000,
      httpOnly: true,
      sameSite: "lax",
      secure: this.configuracao.cookieSeguro,
      path: "/",
    });
    return this.publico(usuario);
  }

  async sair(requisicao: Request, resposta: Response): Promise<void> {
    const token = requisicao.cookies?.[COOKIE_SESSAO];
    if (token) {
      await this.prisma.sessao.deleteMany({ where: { token: this.seguranca.hashDoToken(token) } });
    }
    resposta.clearCookie(COOKIE_SESSAO, { path: "/" });
  }

  private publico(usuario: { id: number; nome: string; email: string; papel: string }): UsuarioPublico {
    const { id, nome, email, papel } = usuario;
    return { id, nome, email, papel: papel as UsuarioPublico["papel"] };
  }
}
