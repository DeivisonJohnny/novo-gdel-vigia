import { randomBytes, scryptSync } from "node:crypto";
import { PrismaClient } from "@prisma/client";

const CUSTO_SCRYPT = { N: 2 ** 14, r: 8, p: 1 };
const TAMANHO_CHAVE = 64;
const TAMANHO_SAL = 16;
const PAPEL_DA_SEMENTE = "admin";

const USUARIOS_DA_SEMENTE = [
  { email: "deivisonjohnny@gmail.com", nome: "Deivison", senha: "true1234" },
  { email: "gabriel@gdel.com.br", nome: "Gabriel", senha: "true1234" },
];

function gerarHash(senha: string): string {
  const sal = randomBytes(TAMANHO_SAL);
  const chave = scryptSync(senha, sal, TAMANHO_CHAVE, CUSTO_SCRYPT);
  return `scrypt$${sal.toString("base64")}$${chave.toString("base64")}`;
}

async function main() {
  const prisma = new PrismaClient();
  try {
    for (const { email, nome, senha } of USUARIOS_DA_SEMENTE) {
      const existente = await prisma.usuario.findUnique({ where: { email } });
      if (existente) {
        console.log(`usuário ${email} já existe: nada a fazer`);
        continue;
      }
      await prisma.usuario.create({
        data: { nome, email, senha: gerarHash(senha), papel: PAPEL_DA_SEMENTE, criadoEm: Date.now() / 1000 },
      });
      console.log(`usuário ${email} criado (${PAPEL_DA_SEMENTE})`);
    }
  } finally {
    await prisma.$disconnect();
  }
}

main();
