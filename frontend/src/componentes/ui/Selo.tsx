import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { DoorOpen } from "lucide-react";
import type { Nivel, Ocorrencia, ParecerIA, Situacao, Veredito, VereditoIA } from "@/lib/tipos";
import { ROTULO_NIVEL, ROTULO_SITUACAO, ROTULO_SITUACAO_IA, ROTULO_VEREDITO, ROTULO_VEREDITO_IA } from "@/lib/rotulos";

type Tom = "alerta" | "atencao" | "sucesso" | "info" | "revisao" | "neutro";

const TONS: Record<Tom, string> = {
  alerta: "bg-alerta/10 text-alerta ring-alerta/25",
  atencao: "bg-atencao/10 text-atencao ring-atencao/25",
  sucesso: "bg-sucesso/10 text-sucesso ring-sucesso/25",
  info: "bg-info/10 text-info ring-info/25",
  revisao: "bg-revisao/10 text-revisao ring-revisao/30",
  neutro: "bg-elevada text-suave ring-borda",
};

export function Selo({ tom = "neutro", children, className }: { tom?: Tom; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONS[tom], className)}>
      {children}
    </span>
  );
}

const TOM_NIVEL: Record<Nivel, Tom> = { alerta: "alerta", atencao: "atencao", ok: "sucesso", reposicao: "info" };
const TOM_SITUACAO: Record<Situacao, Tom> = { aberta: "atencao", triagem: "info", descartada: "neutro", resolvida: "sucesso", revisada: "neutro" };
const TOM_VEREDITO_IA: Record<VereditoIA, Tom> = { furto_provavel: "alerta", falso_positivo: "sucesso", inconclusivo: "neutro" };
const TOM_VEREDITO: Record<Veredito, Tom> = { furto: "alerta", falso_positivo: "sucesso", duvida: "neutro" };

export const SeloNivel = ({ nivel }: { nivel: Nivel }) => <Selo tom={TOM_NIVEL[nivel]}>{ROTULO_NIVEL[nivel]}</Selo>;
export const SeloEntradaSemCompra = () => (
  <Selo tom="revisao">
    <DoorOpen className="h-3 w-3" /> Entrou sem comprar
  </Selo>
);
export const SeloDoTipo = ({ ocorrencia }: { ocorrencia: Pick<Ocorrencia, "tipo" | "nivel"> }) =>
  ocorrencia.tipo === "sem_compra" ? <SeloEntradaSemCompra /> : <SeloNivel nivel={ocorrencia.nivel} />;
export const SeloSituacao = ({ situacao }: { situacao: Situacao }) => (
  <Selo tom={TOM_SITUACAO[situacao]}>{ROTULO_SITUACAO[situacao]}</Selo>
);
export const SeloVeredito = ({ veredito }: { veredito: Veredito }) => (
  <Selo tom={TOM_VEREDITO[veredito]}>{ROTULO_VEREDITO[veredito]}</Selo>
);

export function SeloIA({ ia, situacao }: { ia: ParecerIA | null; situacao: Situacao }) {
  if (situacao === "triagem") return <Selo tom="info">Analisando…</Selo>;
  if (!ia) return <span className="text-xs text-fraco">—</span>;
  if (ia.situacao !== "concluida" || !ia.veredito) return <Selo>{ROTULO_SITUACAO_IA[ia.situacao]}</Selo>;
  return (
    <Selo tom={TOM_VEREDITO_IA[ia.veredito]}>
      {ROTULO_VEREDITO_IA[ia.veredito]} · {ia.confianca}%
    </Selo>
  );
}

export function Indicador({ ativo, rotulo, pulsar = false }: { ativo: boolean; rotulo?: string; pulsar?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-suave">
      <span className={cn("h-2 w-2 rounded-full", ativo ? "bg-sucesso" : "bg-fraco", ativo && pulsar && "animate-pulso")} />
      {rotulo}
    </span>
  );
}
