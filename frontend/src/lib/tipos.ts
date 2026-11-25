export type Papel = "admin" | "operador";
export type Nivel = "alerta" | "atencao" | "ok" | "reposicao";
export type Situacao = "aberta" | "triagem" | "descartada" | "resolvida" | "revisada";
export type VereditoIA = "furto_provavel" | "falso_positivo" | "inconclusivo";
export type Veredito = "furto" | "falso_positivo" | "duvida";
export type ResultadoVisita = "pagas" | "sem_pagamento" | "sem_produto" | "suspeitas";

export interface Usuario {
  id: number;
  nome: string;
  email: string;
  papel: Papel;
}

export interface UsuarioCadastro extends Usuario {
  ativo: number;
  criado_em: number;
  ultimo_acesso: number | null;
}

export interface Loja {
  id: string;
  nome: string;
  pdv_configurado: boolean;
  cameras: string[];
}

export interface Motivo {
  sinal: string;
  peso: number;
  texto: string;
}

export interface EventoCamera {
  t: number;
  camera: string;
  loja: string | null;
  pessoa: string | null;
  tipo: "entrou" | "pegou" | "totem" | "saiu" | "objeto" | "totem_aprendido";
  texto: string;
}

export type Caixa = [number, number, number, number];

export type OrigemTotem = "manual" | "sem_maquininha" | "configurado" | "aprendido" | "procurando";

export interface Camera {
  nome: string;
  descricao: string;
  loja: string | null;
  loja_nome: string;
  online: boolean;
  erro: string;
  fps: number;
  uso_ia: number;
  pessoas: number;
  cobre_totem: boolean;
  origem_totem: OrigemTotem;
  totens: Caixa[];
  caminho: string;
  eventos: EventoCamera[];
}

export interface PessoaDetectada {
  id: string;
  caixa: number[];
  pegadas: number;
  totem: boolean;
  produto: number[] | null;
  no_totem_agora: boolean;
  segundos: number;
}

export interface Deteccao {
  t: number;
  analisou: boolean;
  fps: number;
  uso_ia: number;
  totens: Caixa[];
  origem_totem: OrigemTotem;
  pessoas: PessoaDetectada[];
}

export interface ParecerIA {
  situacao: "concluida" | "erro" | "sem_imagens" | "desligada";
  veredito?: VereditoIA;
  confianca?: number;
  resumo?: string;
  sinais?: string[];
  justificativa?: string;
  modelo?: string;
  analisada_em?: number;
  imagens?: number;
  erro?: string;
}

export type TipoOcorrencia = "suspeita" | "sem_compra";

export interface Ocorrencia {
  id: number;
  tipo: TipoOcorrencia;
  visita_id: string;
  loja: string | null;
  loja_nome: string;
  cameras: string[];
  criada_em: number;
  inicio: number;
  fim: number;
  score: number;
  nivel: Nivel;
  situacao: Situacao;
  motivos: Motivo[];
  evidencias: string[];
  clipes: string[];
  resolucao: string | null;
  resolvida_em: number | null;
  veredito: Veredito | null;
  observacao: string | null;
  revisada_por: string | null;
  revisada_em: number | null;
  ia: ParecerIA | null;
}

export interface Pagamento {
  id: string;
  horario: number;
  valor: number | null;
  situacao: string;
  qtd_itens: number | null;
  pdv: string | null;
  loja: string | null;
  loja_nome: string;
  metodo: string | null;
  itens: { produto_id: number; descricao: string; quantidade: number; preco: number | null }[];
  visita_id: string | null;
}

export interface EventoLinhaDoTempo {
  t: number;
  tipo: "entrou" | "pegou" | "totem" | "saiu";
  camera: string;
  texto: string;
}

export interface OcorrenciaDetalhe extends Ocorrencia {
  pegadas: number | null;
  foi_totem: boolean | null;
  linha_do_tempo: EventoLinhaDoTempo[];
  pagamento: Pagamento | null;
  vendas_proximas: Pagamento[];
}

export interface Visita {
  id: string;
  loja: string | null;
  loja_nome: string;
  inicio: number;
  fim: number;
  cameras: string[];
  pegadas: number;
  foi_totem: number;
  score: number;
  nivel: Nivel;
  pagamento_id: string | null;
  valor: number | null;
  metodo: string | null;
  qtd_itens: number | null;
  pago_em: number | null;
  ocorrencia_id: number | null;
  motivos: Motivo[];
}

export interface Pagina<T> {
  total: number;
  itens: T[];
}

export interface ResumoDia {
  visitas: number;
  visitas_com_produto: number;
  visitas_pagas: number;
  vendas: number;
  faturamento: number;
  ocorrencias: number;
  ocorrencias_abertas: number;
  alertas_abertos: number;
  furtos_confirmados: number;
  falsos_positivos: number;
}

export interface MovimentoHora {
  hora: number;
  visitas: number;
  ocorrencias: number;
}

export interface Painel {
  hoje: ResumoDia;
  por_hora: MovimentoHora[];
  ocorrencias_recentes: Ocorrencia[];
  cameras: Camera[];
  motor: string;
}

export interface StatusSistema {
  versao: string;
  ambiente: string;
  nome: string;
  motor: {
    situacao: string;
    erro?: string;
    iniciado_em?: number | null;
    modelo?: { arquivo: string; classes: string[]; inferencia_ms: number } | null;
    touchpay?: {
      configurado: boolean;
      pdvs: number[];
      recebidos: number;
      ultimo_recebido: number | null;
      ultima_consulta: number | null;
      erro_vendas: string;
      erro_estoque: string;
    };
    coleta?: { ativa: boolean; pasta: string; salvas_agora: number; hoje: Record<string, number>; sem_disco: number };
    visitas_em_andamento?: { id: string; loja: string; cameras: string[]; pegadas: number; decide_em: number }[];
    disco?: { livre_gb: number; total_gb: number };
    clipes_ativos?: boolean;
    triagem?: {
      ativa: boolean;
      modelo: string | null;
      score_acima_de?: number;
      na_fila: number;
      analisadas: number;
      encaminhadas: number;
      descartadas: number;
      erros: number;
      ultimo_erro: string;
    };
  };
  cameras: Camera[];
}

export interface Notificacao<T = Record<string, unknown>> {
  id: number;
  tipo:
    | "ocorrencia"
    | "ocorrencia_triagem"
    | "ocorrencia_descartada"
    | "ocorrencia_resolvida"
    | "ocorrencia_revisada"
    | "visita"
    | "evento_camera"
    | "clipe";
  t: number;
  dados: T;
}

export interface CameraCadastro {
  nome: string;
  descricao: string;
  loja: string;
  loja_nome: string;
  caminho: string;
  cadastrada: boolean;
  url: string | null;
  maquininhas: Caixa[] | null;
}

export interface MarcacaoMaquininhas {
  camera: string;
  origem: "manual" | "sem_maquininha" | "automatica";
  manual: Caixa[] | null;
  automatica: Caixa | null;
}

export interface RecorteSemCompra {
  ativo: boolean;
  espera_s: number;
}

export interface LojaCadastro {
  id: string;
  nome: string;
  pdv: string;
  recorte_sem_compra: RecorteSemCompra;
}

export interface CadastroCameras {
  roteador: { disponivel: boolean; erro: string; sincronizado_em: number | null };
  rtmp_publico_configurado: boolean;
  lojas: LojaCadastro[];
  cameras: CameraCadastro[];
}

export interface CameraCriada {
  nome: string;
  url: string;
  roteador_ok: boolean;
  erro_roteador: string;
}

export interface PdvTouchPay {
  id: string;
  nome: string;
  loja: string | null;
}
