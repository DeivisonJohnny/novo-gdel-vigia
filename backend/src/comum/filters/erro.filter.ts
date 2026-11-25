import { ArgumentsHost, Catch, ExceptionFilter, HttpException, HttpStatus } from "@nestjs/common";
import { Response } from "express";

@Catch()
export class ErroFilter implements ExceptionFilter {
  catch(excecao: unknown, host: ArgumentsHost): void {
    const resposta = host.switchToHttp().getResponse<Response>();
    const status = excecao instanceof HttpException ? excecao.getStatus() : HttpStatus.INTERNAL_SERVER_ERROR;
    const corpo = excecao instanceof HttpException ? excecao.getResponse() : null;
    const detalhe = this.detalhe(corpo, excecao);
    resposta.status(status).json({ detail: detalhe });
  }

  private detalhe(corpo: unknown, excecao: unknown): string | string[] {
    if (typeof corpo === "string") return corpo;
    if (corpo && typeof corpo === "object" && "message" in corpo) {
      const mensagem = (corpo as { message: unknown }).message;
      if (typeof mensagem === "string" || Array.isArray(mensagem)) return mensagem;
    }
    return excecao instanceof Error ? excecao.message : "erro interno";
  }
}
