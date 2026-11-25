import { readFileSync } from "node:fs";
import { join } from "node:path";

const HORAS_DE_SESSAO_PADRAO = 12;
const PORTA_PADRAO = 3000;

export const carregarEnv = (arquivo: string = join(__dirname, "..", ".env")): void => {
  let conteudo: string;
  try {
    conteudo = readFileSync(arquivo, "utf-8");
  } catch {
    return;
  }
  for (const linha of conteudo.split("\n")) {
    const limpa = linha.trim();
    if (!limpa || limpa.startsWith("#") || !limpa.includes("=")) continue;
    const [chave, ...resto] = limpa.split("=");
    const valor = resto.join("=").trim().replace(/^['"]|['"]$/g, "");
    if (!(chave.trim() in process.env)) process.env[chave.trim()] = valor;
  }
};

const ligado = (valor: string | undefined): boolean => {
  return ["1", "true", "sim", "yes", "on"].includes((valor ?? "").trim().toLowerCase());
};

export interface Configuracao {
  porta: number;
  host: string;
  cookieSeguro: boolean;
  sessaoHoras: number;
}

export const carregarConfiguracao = (): Configuracao => ({
  porta: Number(process.env.VIGIA_PORTA_BACKEND) || PORTA_PADRAO,
  host: process.env.VIGIA_HOST_BACKEND || "127.0.0.1",
  cookieSeguro: ligado(process.env.VIGIA_COOKIE_SEGURO),
  sessaoHoras: Number(process.env.VIGIA_SESSAO_HORAS) || HORAS_DE_SESSAO_PADRAO,
});
