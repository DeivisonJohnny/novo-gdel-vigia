export interface UsuarioPublico {
  id: number;
  nome: string;
  email: string;
  papel: "admin" | "operador";
}

export const COOKIE_SESSAO = "vigia_sessao";
