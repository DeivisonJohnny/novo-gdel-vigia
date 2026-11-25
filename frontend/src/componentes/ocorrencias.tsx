import { Camera as IconeCamera } from "lucide-react";
import type { Motivo } from "@/lib/tipos";
import { urlArquivo } from "@/lib/api";
import { cn } from "@/lib/cn";

export function Miniatura({ caminho, className }: { caminho?: string | null; className?: string }) {
  return (
    <div className={cn("flex shrink-0 items-center justify-center overflow-hidden rounded-md bg-elevada", className)}>
      {caminho ? (
        <img src={urlArquivo(caminho)} alt="" loading="lazy" className="h-full w-full object-cover" />
      ) : (
        <IconeCamera className="h-4 w-4 text-fraco" />
      )}
    </div>
  );
}

export function motivoPrincipal(motivos: Motivo[]) {
  const comPeso = motivos.filter((m) => m.peso > 0).sort((a, b) => b.peso - a.peso);
  return (comPeso[0] ?? motivos[0])?.texto ?? "—";
}

export function ListaMotivos({ motivos }: { motivos: Motivo[] }) {
  return (
    <ul className="divide-y">
      {motivos.map((motivo, indice) => (
        <li key={`${motivo.sinal}-${indice}`} className="flex items-start justify-between gap-4 py-2.5 text-sm">
          <span>{motivo.texto}</span>
          <span
            className={cn(
              "shrink-0 font-mono text-xs",
              motivo.peso > 0 ? "text-alerta" : motivo.peso < 0 ? "text-sucesso" : "text-fraco",
            )}
          >
            {motivo.peso > 0 ? `+${motivo.peso}` : motivo.peso || "·"}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function BarraScore({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-elevada">
        <div
          className={cn("h-full rounded-full", score >= 70 ? "bg-alerta" : score >= 40 ? "bg-atencao" : "bg-sucesso")}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className="font-mono text-xs text-suave">{score}</span>
    </div>
  );
}
