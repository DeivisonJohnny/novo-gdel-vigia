import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import { Botao } from "./Botao";

export function Modal({ aberto, titulo, aoFechar, children, className }: {
  aberto: boolean;
  titulo: string;
  aoFechar: () => void;
  children: ReactNode;
  className?: string;
}) {
  useEffect(() => {
    if (!aberto) return;
    const teclar = (evento: KeyboardEvent) => evento.key === "Escape" && aoFechar();
    window.addEventListener("keydown", teclar);
    return () => window.removeEventListener("keydown", teclar);
  }, [aberto, aoFechar]);

  if (!aberto) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" onMouseDown={aoFechar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        className={cn("w-full max-w-md animate-entrar rounded-xl border bg-superficie shadow-2xl", className)}
        onMouseDown={(evento) => evento.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-sm font-semibold">{titulo}</h2>
          <Botao variante="fantasma" tamanho="sm" onClick={aoFechar} aria-label="Fechar">
            <X className="h-4 w-4" />
          </Botao>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
