import { ShieldCheck } from "lucide-react";

export function Marca() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primaria text-primaria-texto shadow-sm">
        <ShieldCheck className="h-4.5 w-4.5" />
      </div>
      <div className="leading-tight">
        <p className="text-sm font-semibold">GDEL Vigia</p>
        <p className="text-[11px] text-fraco">Lojas autônomas</p>
      </div>
    </div>
  );
}
