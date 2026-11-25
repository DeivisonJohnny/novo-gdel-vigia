import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatarNumero } from "@/lib/formato";
import { Botao } from "./Botao";

const CAMPO = "foco h-9 rounded-lg border bg-superficie px-3 text-sm text-texto placeholder:text-fraco";

export function Campo({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(CAMPO, className)} {...props} />;
}

export function Selecao({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(CAMPO, "pr-8", className)} {...props}>
      {children}
    </select>
  );
}

export function Rotulo({ texto, children, className }: { texto: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1.5 text-xs font-medium text-suave", className)}>
      {texto}
      {children}
    </label>
  );
}

export function Segmentado<T extends string>({
  opcoes,
  valor,
  aoMudar,
}: {
  opcoes: { valor: T; rotulo: ReactNode }[];
  valor: T;
  aoMudar: (valor: T) => void;
}) {
  return (
    <div role="tablist" className="inline-flex max-w-full overflow-x-auto rounded-lg border bg-elevada p-0.5">
      {opcoes.map((opcao) => (
        <button
          key={opcao.valor}
          role="tab"
          aria-selected={valor === opcao.valor}
          onClick={() => aoMudar(opcao.valor)}
          className={cn(
            "foco shrink-0 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            valor === opcao.valor ? "bg-superficie text-texto shadow-sm" : "text-suave hover:text-texto",
          )}
        >
          {opcao.rotulo}
        </button>
      ))}
    </div>
  );
}

export function Paginacao({
  pagina,
  porPagina,
  total,
  aoMudar,
}: {
  pagina: number;
  porPagina: number;
  total: number;
  aoMudar: (pagina: number) => void;
}) {
  const ultima = Math.max(1, Math.ceil(total / porPagina));
  const primeiroItem = total ? (pagina - 1) * porPagina + 1 : 0;
  return (
    <footer className="flex items-center justify-between border-t px-5 py-3 text-xs text-suave">
      <span>
        {formatarNumero(primeiroItem)}–{formatarNumero(Math.min(pagina * porPagina, total))} de {formatarNumero(total)}
      </span>
      <div className="flex items-center gap-1">
        <Botao variante="fantasma" tamanho="sm" disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)} aria-label="Página anterior">
          <ChevronLeft className="h-4 w-4" />
        </Botao>
        <span className="px-2">
          {pagina} / {ultima}
        </span>
        <Botao variante="fantasma" tamanho="sm" disabled={pagina >= ultima} onClick={() => aoMudar(pagina + 1)} aria-label="Próxima página">
          <ChevronRight className="h-4 w-4" />
        </Botao>
      </div>
    </footer>
  );
}
