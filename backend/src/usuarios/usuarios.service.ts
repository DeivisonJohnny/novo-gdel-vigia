import { ConflictException, Injectable } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { PrismaService } from "../prisma/prisma.service";
import { SegurancaService } from "../seguranca/seguranca.service";
import { AtualizarUsuarioDto } from "./dto/atualizar-usuario.dto";
import { CriarUsuarioDto } from "./dto/criar-usuario.dto";

const CODIGO_VIOLACAO_UNICIDADE = "P2002";

@Injectable()
export class UsuariosService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly seguranca: SegurancaService,
  ) {}

  listar() {
    return this.prisma.usuario.findMany({
      select: { id: true, nome: true, email: true, papel: true, ativo: true, criadoEm: true, ultimoAcesso: true },
      orderBy: { nome: "asc" },
    });
  }

  async criar(dados: CriarUsuarioDto) {
    try {
      const usuario = await this.prisma.usuario.create({
        data: {
          nome: dados.nome.trim(),
          email: dados.email.trim().toLowerCase(),
          senha: this.seguranca.gerarHash(dados.senha),
          papel: dados.papel,
          criadoEm: Date.now() / 1000,
        },
      });
      return { id: usuario.id };
    } catch (erro) {
      if (erro instanceof Prisma.PrismaClientKnownRequestError && erro.code === CODIGO_VIOLACAO_UNICIDADE) {
        throw new ConflictException("já existe um usuário com este e-mail");
      }
      throw erro;
    }
  }

  async alterar(usuarioId: number, dados: AtualizarUsuarioDto) {
    const campos: Prisma.UsuarioUpdateInput = {};
    if (dados.nome !== undefined) campos.nome = dados.nome;
    if (dados.papel !== undefined) campos.papel = dados.papel;
    if (dados.ativo !== undefined) campos.ativo = dados.ativo;
    if (dados.senha !== undefined) campos.senha = this.seguranca.gerarHash(dados.senha);

    await this.prisma.usuario.update({ where: { id: usuarioId }, data: campos });

    if (dados.ativo === false) {
      await this.prisma.sessao.deleteMany({ where: { usuarioId } });
    }
  }

  buscar(usuarioId: number) {
    return this.prisma.usuario.findUnique({ where: { id: usuarioId } });
  }
}
