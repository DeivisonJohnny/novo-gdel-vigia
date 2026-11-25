import { Injectable } from "@nestjs/common";

const TENTATIVAS_LOGIN = 5;
const JANELA_TENTATIVAS_MS = 300_000;

@Injectable()
export class LimiteDeTentativasService {
  private readonly falhas = new Map<string, number[]>();

  private limpar(chave: string, agora: number): number[] {
    const restantes = (this.falhas.get(chave) ?? []).filter((quando) => agora - quando <= JANELA_TENTATIVAS_MS);
    this.falhas.set(chave, restantes);
    return restantes;
  }

  bloqueado(chave: string): boolean {
    return this.limpar(chave, Date.now()).length >= TENTATIVAS_LOGIN;
  }

  falhou(chave: string): void {
    const agora = Date.now();
    this.limpar(chave, agora).push(agora);
  }

  liberar(chave: string): void {
    this.falhas.delete(chave);
  }
}
