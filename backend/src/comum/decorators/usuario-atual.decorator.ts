import { ExecutionContext, createParamDecorator } from "@nestjs/common";
import { RequisicaoComUsuario } from "../interfaces/requisicao-com-usuario.interface";

export const UsuarioAtual = createParamDecorator((_dado: unknown, contexto: ExecutionContext) => {
  return contexto.switchToHttp().getRequest<RequisicaoComUsuario>().usuario;
});
