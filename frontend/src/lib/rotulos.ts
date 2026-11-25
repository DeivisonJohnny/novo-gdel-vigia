import type { Nivel, ParecerIA, Situacao, Veredito, VereditoIA } from "./tipos";

export const ROTULO_NIVEL: Record<Nivel, string> = {
  alerta: "Alerta",
  atencao: "Atenção",
  ok: "Normal",
  reposicao: "Reposição",
};

export const ROTULO_SITUACAO: Record<Situacao, string> = {
  aberta: "Aberta",
  triagem: "Na triagem da IA",
  descartada: "Descartada pela IA",
  resolvida: "Resolvida",
  revisada: "Revisada",
};

export const ROTULO_VEREDITO: Record<Veredito, string> = {
  furto: "Furto confirmado",
  falso_positivo: "Falso positivo",
  duvida: "Inconclusivo",
};

export const ROTULO_VEREDITO_IA: Record<VereditoIA, string> = {
  furto_provavel: "Furto provável",
  falso_positivo: "Falso positivo",
  inconclusivo: "Inconclusivo",
};

export const ROTULO_SITUACAO_IA: Record<ParecerIA["situacao"], string> = {
  concluida: "Analisada pela IA",
  erro: "IA falhou",
  sem_imagens: "Sem imagens para a IA",
  desligada: "Triagem desligada",
};

export const ROTULO_METODO: Record<string, string> = {
  Credit: "Crédito",
  Debit: "Débito",
  Pix: "Pix",
  Voucher: "Voucher",
  AppSale: "App",
  AppPix: "Pix no app",
  AppCreditCard: "Cartão no app",
  Wallet: "Carteira",
};

export const rotuloMetodo = (metodo: string | null) => (metodo ? ROTULO_METODO[metodo] ?? metodo : "—");
