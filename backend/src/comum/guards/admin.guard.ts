import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from "@nestjs/common";
import { RequisicaoComUsuario } from "../interfaces/requisicao-com-usuario.interface";

@Injectable()
export class AdminGuard implements CanActivate {
  canActivate(contexto: ExecutionContext): boolean {
    const requisicao = contexto.switchToHttp().getRequest<RequisicaoComUsuario>();
    if (requisicao.usuario.papel !== "admin") {
      throw new ForbiddenException("apenas administradores");
    }
    return true;
  }
}
