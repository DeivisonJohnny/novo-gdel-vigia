import {
  BadRequestException,
  Body,
  Controller,
  Get,
  HttpCode,
  NotFoundException,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  UnprocessableEntityException,
  UseGuards,
} from "@nestjs/common";
import { AdminGuard } from "../comum/guards/admin.guard";
import { SessaoGuard } from "../comum/guards/sessao.guard";
import { UsuarioAtual } from "../comum/decorators/usuario-atual.decorator";
import { UsuarioPublico } from "../comum/interfaces/usuario-publico.interface";
import { SenhaFraca } from "../seguranca/seguranca.service";
import { AtualizarUsuarioDto } from "./dto/atualizar-usuario.dto";
import { CriarUsuarioDto } from "./dto/criar-usuario.dto";
import { UsuariosService } from "./usuarios.service";

@Controller("api/usuarios")
@UseGuards(SessaoGuard, AdminGuard)
export class UsuariosController {
  constructor(private readonly usuarios: UsuariosService) {}

  @Get()
  listar() {
    return this.usuarios.listar();
  }

  @Post()
  @HttpCode(201)
  async criar(@Body() dados: CriarUsuarioDto) {
    try {
      return await this.usuarios.criar(dados);
    } catch (erro) {
      if (erro instanceof SenhaFraca) {
        throw new UnprocessableEntityException(erro.message);
      }
      throw erro;
    }
  }

  @Patch(":id")
  async alterar(
    @Param("id", ParseIntPipe) usuarioId: number,
    @Body() dados: AtualizarUsuarioDto,
    @UsuarioAtual() admin: UsuarioPublico,
  ) {
    const existente = await this.usuarios.buscar(usuarioId);
    if (!existente) {
      throw new NotFoundException("usuário não encontrado");
    }
    const proprio = usuarioId === admin.id;
    if (proprio && (dados.ativo === false || dados.papel === "operador")) {
      throw new BadRequestException("você não pode desativar nem rebaixar a própria conta");
    }
    try {
      await this.usuarios.alterar(usuarioId, dados);
    } catch (erro) {
      if (erro instanceof SenhaFraca) {
        throw new UnprocessableEntityException(erro.message);
      }
      throw erro;
    }
    return { ok: true };
  }
}
