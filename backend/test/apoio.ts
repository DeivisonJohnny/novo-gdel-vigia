import { HttpStatus, INestApplication, ValidationPipe } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { NestExpressApplication } from "@nestjs/platform-express";
import cookieParser from "cookie-parser";
import { AppModule } from "../src/app.module";
import { ErroFilter } from "../src/comum/filters/erro.filter";
import { PrismaService } from "../src/prisma/prisma.service";

const TABELAS = ["sessoes", "usuarios", "pagamentos", "movimentacoes", "visitas", "ocorrencias",
                 "lojas_cadastradas", "cameras_cadastradas", "maquininhas_marcadas", "recorte_sem_compra"];

export async function criarAppDeTeste(): Promise<INestApplication> {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, { logger: false });
  app.use(cookieParser());
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true, errorHttpStatusCode: HttpStatus.UNPROCESSABLE_ENTITY }));
  app.useGlobalFilters(new ErroFilter());
  await app.init();
  return app;
}

export async function limparBanco(app: INestApplication): Promise<void> {
  const prisma = app.get(PrismaService);
  await prisma.$executeRawUnsafe(`TRUNCATE ${TABELAS.join(", ")} RESTART IDENTITY CASCADE`);
}

export function cookieDaResposta(resposta: { headers: Record<string, unknown> }): string {
  const bruto = resposta.headers["set-cookie"] as string[] | string | undefined;
  const lista = Array.isArray(bruto) ? bruto : bruto ? [bruto] : [];
  const cookie = lista.find((c) => c.startsWith("vigia_sessao="));
  if (!cookie) throw new Error("cookie de sessão não encontrado na resposta");
  return cookie.split(";")[0];
}
