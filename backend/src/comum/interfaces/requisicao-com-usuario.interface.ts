import { Request } from "express";
import { UsuarioPublico } from "./usuario-publico.interface";

export interface RequisicaoComUsuario extends Request {
  usuario: UsuarioPublico;
}
