import "reflect-metadata";
import { HttpStatus, ValidationPipe } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { NestExpressApplication } from "@nestjs/platform-express";
import cookieParser from "cookie-parser";
import { AppModule } from "./app.module";
import { ErroFilter } from "./comum/filters/erro.filter";
import { carregarConfiguracao, carregarEnv } from "./configuracao";

carregarEnv();

const CABECALHOS_SEGURANCA = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "same-origin",
};

async function bootstrap() {
  const configuracao = carregarConfiguracao();
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  app.use(cookieParser());
  app.use((_requisicao: unknown, resposta: { set: (headers: Record<string, string>) => void }, proximo: () => void) => {
    resposta.set(CABECALHOS_SEGURANCA);
    proximo();
  });
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true, errorHttpStatusCode: HttpStatus.UNPROCESSABLE_ENTITY }));
  app.useGlobalFilters(new ErroFilter());
  app.set("trust proxy", process.env.VIGIA_PROXIES_CONFIAVEIS ?? "127.0.0.1");
  await app.listen(configuracao.porta, configuracao.host);
}

bootstrap();
