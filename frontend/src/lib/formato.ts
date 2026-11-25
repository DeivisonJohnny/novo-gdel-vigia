const FUSO = "America/Sao_Paulo";

const hora = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dataHora = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const dataCompleta = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, dateStyle: "full", timeStyle: "medium" });
const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const numero = new Intl.NumberFormat("pt-BR");
const relativo = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

export const formatarHora = (t: number) => hora.format(t * 1000);
export const formatarDataHora = (t: number) => dataHora.format(t * 1000);
export const formatarDataCompleta = (t: number) => dataCompleta.format(t * 1000);
export const formatarMoeda = (valor: number | null | undefined) => moeda.format(valor ?? 0);
export const formatarNumero = (valor: number) => numero.format(valor);

export function formatarDuracao(segundos: number) {
  const total = Math.max(0, Math.round(segundos));
  const minutos = Math.floor(total / 60);
  return minutos ? `${minutos}min ${String(total % 60).padStart(2, "0")}s` : `${total}s`;
}

export function haQuantoTempo(t: number) {
  const segundos = Math.round(t - Date.now() / 1000);
  const passos: [number, Intl.RelativeTimeFormatUnit][] = [[60, "second"], [60, "minute"], [24, "hour"], [Infinity, "day"]];
  let valor = segundos;
  for (const [limite, unidade] of passos) {
    if (Math.abs(valor) < limite) return relativo.format(valor, unidade);
    valor = Math.round(valor / limite);
  }
  return relativo.format(valor, "day");
}

export function hojeIso() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO }).format(new Date());
}

export function diasAtrasIso(dias: number) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO }).format(new Date(Date.now() - dias * 86400000));
}

export const porcentagem = (parte: number, total: number) => (total ? Math.round((parte / total) * 100) : 0);
