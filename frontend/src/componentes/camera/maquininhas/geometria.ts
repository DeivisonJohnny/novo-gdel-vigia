import type { Caixa } from "@/lib/tipos";

export const MAX_MAQUININHAS = 6;
export const LADO_MINIMO = 0.01;
const CASAS = 4;

export interface Ponto {
  x: number;
  y: number;
}

export type Canto = "no" | "ne" | "so" | "se";

export const CANTOS: Canto[] = ["no", "ne", "so", "se"];

export const limitar = (valor: number, minimo = 0, maximo = 1) => Math.min(Math.max(valor, minimo), maximo);

const arredondar = (valor: number) => Number(valor.toFixed(CASAS));

export function caixaEntre(inicio: Ponto, fim: Ponto): Caixa {
  return [
    arredondar(Math.min(inicio.x, fim.x)),
    arredondar(Math.min(inicio.y, fim.y)),
    arredondar(Math.max(inicio.x, fim.x)),
    arredondar(Math.max(inicio.y, fim.y)),
  ];
}

export const temTamanho = ([x1, y1, x2, y2]: Caixa) => x2 - x1 >= LADO_MINIMO && y2 - y1 >= LADO_MINIMO;

export function moverCaixa([x1, y1, x2, y2]: Caixa, deslocamento: Ponto): Caixa {
  const largura = x2 - x1;
  const altura = y2 - y1;
  const esquerda = limitar(x1 + deslocamento.x, 0, 1 - largura);
  const topo = limitar(y1 + deslocamento.y, 0, 1 - altura);
  return [arredondar(esquerda), arredondar(topo), arredondar(esquerda + largura), arredondar(topo + altura)];
}

const CANTO_OPOSTO: Record<Canto, (caixa: Caixa) => Ponto> = {
  no: ([, , x2, y2]) => ({ x: x2, y: y2 }),
  ne: ([x1, , , y2]) => ({ x: x1, y: y2 }),
  so: ([, y1, x2]) => ({ x: x2, y: y1 }),
  se: ([x1, y1]) => ({ x: x1, y: y1 }),
};

export const redimensionarCaixa = (caixa: Caixa, canto: Canto, ponto: Ponto) => caixaEntre(CANTO_OPOSTO[canto](caixa), ponto);

export const cantoValido = (valor: string | undefined) => CANTOS.find((canto) => canto === valor);

export const posicao = ([x1, y1, x2, y2]: Caixa) => ({
  left: `${x1 * 100}%`,
  top: `${y1 * 100}%`,
  width: `${(x2 - x1) * 100}%`,
  height: `${(y2 - y1) * 100}%`,
});

export const mesmaMarcacao = (a: Caixa[], b: Caixa[]) => JSON.stringify(a) === JSON.stringify(b);
