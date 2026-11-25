import "reflect-metadata";
import { createInterface } from "node:readline";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";
import { carregarEnv } from "./configuracao";
import { PrismaService } from "./prisma/prisma.service";
import { SegurancaService, SenhaFraca } from "./seguranca/seguranca.service";

carregarEnv();

function perguntarSenhaOculta(mensagem: string): Promise<string> {
  return new Promise((resolve) => {
    const leitor = createInterface({ input: process.stdin, output: process.stdout, terminal: true }) as ReturnType<
      typeof createInterface
    > & { _writeToOutput: (texto: string) => void };
    process.stdout.write(mensagem);
    leitor._writeToOutput = () => {};
    leitor.question("", (resposta) => {
      leitor.close();
      process.stdout.write("\n");
      resolve(resposta);
    });
  });
}

async function pedirSenha(): Promise<string> {
  const senha = await perguntarSenhaOculta("Senha (mín. 8 caracteres): ");
  const repetida = await perguntarSenhaOculta("Repita a senha: ");
  if (senha !== repetida) {
    throw new Error("as senhas não conferem");
  }
  return senha;
}

async function criarUsuario(prisma: PrismaService, seguranca: SegurancaService, email: string, nome: string | undefined, papel: string) {
  const senhaHash = seguranca.gerarHash(await pedirSenha());
  const emailNormalizado = email.trim().toLowerCase();
  const existente = await prisma.usuario.findUnique({ where: { email: emailNormalizado } });
  if (existente) {
    await prisma.usuario.update({ where: { id: existente.id }, data: { senha: senhaHash, papel, ativo: true } });
    console.log(`usuário ${emailNormalizado} atualizado`);
  } else {
    await prisma.usuario.create({
      data: { nome: nome || emailNormalizado.split("@")[0], email: emailNormalizado, senha: senhaHash, papel, criadoEm: Date.now() / 1000 },
    });
    console.log(`usuário ${emailNormalizado} criado (${papel})`);
  }
}

async function main() {
  const [comando, ...resto] = process.argv.slice(2);
  const app = await NestFactory.createApplicationContext(AppModule);
  const prisma = app.get(PrismaService);
  const seguranca = app.get(SegurancaService);

  try {
    const email = comando;
    if (!email) {
      console.error("uso: npm run usuario <email> [--nome NOME] [--papel admin|operador]");
      process.exitCode = 1;
      return;
    }
    const nomeIndice = resto.indexOf("--nome");
    const papelIndice = resto.indexOf("--papel");
    const nome = nomeIndice >= 0 ? resto[nomeIndice + 1] : undefined;
    const papel = papelIndice >= 0 ? resto[papelIndice + 1] : "admin";
    if (!["admin", "operador"].includes(papel)) {
      console.error("--papel deve ser admin ou operador");
      process.exitCode = 1;
      return;
    }
    await criarUsuario(prisma, seguranca, email, nome, papel);
  } catch (erro) {
    if (erro instanceof SenhaFraca || erro instanceof Error) {
      console.error(erro.message);
      process.exitCode = 1;
      return;
    }
    throw erro;
  } finally {
    await app.close();
  }
}

main();
