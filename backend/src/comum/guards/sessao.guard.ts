import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from "@nestjs/common";
import { PrismaService } from "../../prisma/prisma.service";
import { SegurancaService } from "../../seguranca/seguranca.service";
import { RequisicaoComUsuario } from "../interfaces/requisicao-com-usuario.interface";
import { COOKIE_SESSAO, UsuarioPublico } from "../interfaces/usuario-publico.interface";

@Injectable()
export class SessaoGuard implements CanActivate {
  constructor(
    private readonly prisma: PrismaService,
    private readonly seguranca: SegurancaService,
  ) {}

  async canActivate(contexto: ExecutionContext): Promise<boolean> {
    const requisicao = contexto.switchToHttp().getRequest<RequisicaoComUsuario>();
    const token = requisicao.cookies?.[COOKIE_SESSAO];
    const usuario = token ? await this.usuarioDaSessao(token) : null;
    if (!usuario) {
      throw new UnauthorizedException("sessão expirada");
    }
    requisicao.usuario = usuario;
    return true;
  }

  private async usuarioDaSessao(token: string): Promise<UsuarioPublico | null> {
    const sessao = await this.prisma.sessao.findFirst({
      where: {
        token: this.seguranca.hashDoToken(token),
        expiraEm: { gt: Date.now() / 1000 },
        usuario: { ativo: true },
      },
      include: { usuario: true },
    });
    if (!sessao) return null;
    const { id, nome, email, papel } = sessao.usuario;
    return { id, nome, email, papel: papel as UsuarioPublico["papel"] };
  }
}
