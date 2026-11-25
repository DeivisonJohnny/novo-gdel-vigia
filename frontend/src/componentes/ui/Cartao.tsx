import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Cartao({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("rounded-xl border bg-superficie shadow-cartao", className)} {...props} />;
}

export function CabecalhoCartao({ titulo, descricao, acoes }: { titulo: ReactNode; descricao?: ReactNode; acoes?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-4">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold">{titulo}</h2>
        {descricao && <p className="mt-0.5 text-xs text-suave">{descricao}</p>}
      </div>
      {acoes && <div className="flex items-center gap-2">{acoes}</div>}
    </header>
  );
}
