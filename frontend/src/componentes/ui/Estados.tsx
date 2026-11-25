import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import { cn } from "@/lib/cn";

export function EstadoVazio({ titulo, descricao, icone }: { titulo: string; descricao?: string; icone?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="rounded-full bg-elevada p-3 text-fraco">{icone ?? <Inbox className="h-5 w-5" />}</div>
      <p className="text-sm font-medium">{titulo}</p>
      {descricao && <p className="max-w-sm text-xs text-suave">{descricao}</p>}
    </div>
  );
}

export function EstadoErro({ mensagem }: { mensagem: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-alerta/30 bg-alerta/5 px-4 py-3 text-sm text-alerta">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      {mensagem}
    </div>
  );
}

export function Esqueleto({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-elevada", className)} />;
}

export function LinhasCarregando({ linhas = 5 }: { linhas?: number }) {
  return (
    <div className="space-y-3 p-5">
      {Array.from({ length: linhas }, (_, indice) => (
        <Esqueleto key={indice} className="h-10 w-full" />
      ))}
    </div>
  );
}
