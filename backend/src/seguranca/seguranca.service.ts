import { randomBytes, randomUUID, scryptSync, timingSafeEqual, createHash } from "node:crypto";
import { Injectable } from "@nestjs/common";

const CUSTO_SCRYPT = { N: 2 ** 14, r: 8, p: 1 };
const TAMANHO_CHAVE = 64;
const TAMANHO_SAL = 16;
export const TAMANHO_MINIMO_SENHA = 8;

export class SenhaFraca extends Error {}

const scrypt = (senha: string, sal: Buffer): Buffer =>
  scryptSync(senha, sal, TAMANHO_CHAVE, CUSTO_SCRYPT);

@Injectable()
export class SegurancaService {
  gerarHash(senha: string): string {
    if (senha.length < TAMANHO_MINIMO_SENHA) {
      throw new SenhaFraca(`a senha precisa ter pelo menos ${TAMANHO_MINIMO_SENHA} caracteres`);
    }
    const sal = randomBytes(TAMANHO_SAL);
    const chave = scrypt(senha, sal);
    return `scrypt$${sal.toString("base64")}$${chave.toString("base64")}`;
  }

  conferirSenha(senha: string, guardado: string): boolean {
    const partes = guardado.split("$");
    if (partes.length !== 3) return false;
    const [, salBase64, chaveBase64] = partes;
    try {
      const sal = Buffer.from(salBase64, "base64");
      const chaveEsperada = Buffer.from(chaveBase64, "base64");
      const calculada = scrypt(senha, sal);
      return calculada.length === chaveEsperada.length && timingSafeEqual(calculada, chaveEsperada);
    } catch {
      return false;
    }
  }

  novoToken(): string {
    return randomUUID() + randomUUID();
  }

  hashDoToken(token: string): string {
    return createHash("sha256").update(token).digest("hex");
  }
}
