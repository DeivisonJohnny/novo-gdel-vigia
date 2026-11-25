import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variante = "primaria" | "secundaria" | "fantasma" | "perigo";
type Tamanho = "sm" | "md";

const VARIANTES: Record<Variante, string> = {
  primaria: "bg-primaria text-primaria-texto hover:bg-primaria/90 shadow-sm",
  secundaria: "bg-superficie border border-borda text-texto hover:bg-elevada",
  fantasma: "text-suave hover:bg-elevada hover:text-texto",
  perigo: "bg-alerta text-white hover:bg-alerta/90 shadow-sm",
};

const TAMANHOS: Record<Tamanho, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamanho?: Tamanho;
}

export const Botao = forwardRef<HTMLButtonElement, Props>(function Botao(
  { variante = "secundaria", tamanho = "md", className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        "foco inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        VARIANTES[variante],
        TAMANHOS[tamanho],
        className,
      )}
      {...props}
    />
  );
});
