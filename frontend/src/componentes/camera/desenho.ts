import type { Caixa, Deteccao, PessoaDetectada } from "@/lib/tipos";

const COR_TOTEM = "#22c55e";
const COR_PRODUTO = "#ff3cff";
const COR_PEGOU = "#f59e0b";
const COR_NEUTRA = "#e5e7eb";
const FONTE = "600 12px 'Geist Variable', system-ui, sans-serif";

export interface Area {
  x: number;
  y: number;
  largura: number;
  altura: number;
}

export function areaDoConteudo(larguraTela: number, alturaTela: number, larguraVideo: number, alturaVideo: number): Area {
  if (!larguraVideo || !alturaVideo) return { x: 0, y: 0, largura: larguraTela, altura: alturaTela };
  const escala = Math.min(larguraTela / larguraVideo, alturaTela / alturaVideo);
  const largura = larguraVideo * escala;
  const altura = alturaVideo * escala;
  return { x: (larguraTela - largura) / 2, y: (alturaTela - altura) / 2, largura, altura };
}

function retangulo(area: Area, caixa: number[]) {
  const [x1, y1, x2, y2] = caixa;
  return [area.x + x1 * area.largura, area.y + y1 * area.altura, (x2 - x1) * area.largura, (y2 - y1) * area.altura] as const;
}

function etiqueta(ctx: CanvasRenderingContext2D, texto: string, x: number, y: number, cor: string) {
  ctx.font = FONTE;
  const largura = ctx.measureText(texto).width + 10;
  const topo = Math.max(y - 20, 0);
  ctx.fillStyle = cor;
  ctx.beginPath();
  ctx.roundRect(x, topo, largura, 18, 4);
  ctx.fill();
  ctx.fillStyle = "#0b0d11";
  ctx.fillText(texto, x + 5, topo + 13);
}

function corDaPessoa(pessoa: PessoaDetectada) {
  if (pessoa.no_totem_agora || pessoa.totem) return COR_TOTEM;
  return pessoa.pegadas ? COR_PEGOU : COR_NEUTRA;
}

function desenharPessoa(ctx: CanvasRenderingContext2D, area: Area, pessoa: PessoaDetectada) {
  const cor = corDaPessoa(pessoa);
  const [x, y, w, h] = retangulo(area, pessoa.caixa);
  ctx.strokeStyle = cor;
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, w, h);
  const partes = [`#${pessoa.id}`, `${pessoa.segundos}s`];
  if (pessoa.pegadas) partes.push(`pegou ${pessoa.pegadas}`);
  if (pessoa.no_totem_agora) partes.push("no totem");
  etiqueta(ctx, partes.join(" · "), x, y, cor);
  if (!pessoa.produto) return;
  const [px, py, pw, ph] = retangulo(area, pessoa.produto);
  ctx.strokeStyle = COR_PRODUTO;
  ctx.lineWidth = 2;
  ctx.strokeRect(px, py, pw, ph);
  etiqueta(ctx, "produto na mão", px, py, COR_PRODUTO);
}

function desenharTotem(ctx: CanvasRenderingContext2D, area: Area, totem: Caixa) {
  const [x, y, w, h] = retangulo(area, totem);
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = COR_TOTEM;
  ctx.lineWidth = 1.5;
  ctx.strokeRect(x, y, w, h);
  ctx.setLineDash([]);
  ctx.fillStyle = "rgba(34, 197, 94, 0.12)";
  ctx.fillRect(x, y, w, h);
}

export function desenharDeteccao(ctx: CanvasRenderingContext2D, area: Area, deteccao: Deteccao) {
  deteccao.totens.forEach((totem) => desenharTotem(ctx, area, totem));
  deteccao.pessoas.forEach((pessoa) => desenharPessoa(ctx, area, pessoa));
}
