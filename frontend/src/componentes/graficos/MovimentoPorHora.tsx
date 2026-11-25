import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import type { MovimentoHora } from "@/lib/tipos";

const SERIES = [
  { chave: "visitas", rotulo: "Visitas", cor: "var(--serie-1)" },
  { chave: "ocorrencias", rotulo: "Ocorrências", cor: "var(--serie-2)" },
] as const;

const hora = (h: number) => `${String(h).padStart(2, "0")}h`;

function Dica({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-superficie px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-medium">
        {hora(Number(label))} – {hora(Number(label) + 1)}
      </p>
      {SERIES.map((serie) => (
        <p key={serie.chave} className="flex items-center gap-2 text-suave">
          <span className="h-2 w-2 rounded-sm" style={{ background: serie.cor }} />
          {serie.rotulo}
          <span className="ml-auto pl-4 font-medium text-texto">{payload.find((p) => p.dataKey === serie.chave)?.value ?? 0}</span>
        </p>
      ))}
    </div>
  );
}

export function MovimentoPorHora({ dados }: { dados: MovimentoHora[] }) {
  const horaAtual = new Date().getHours();
  const visiveis = dados.filter((d) => d.hora <= horaAtual);
  return (
    <div>
      <ul className="mb-3 flex gap-4 text-xs text-suave" aria-label="Legenda">
        {SERIES.map((serie) => (
          <li key={serie.chave} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: serie.cor }} />
            {serie.rotulo}
          </li>
        ))}
      </ul>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={visiveis} barGap={2} barCategoryGap="20%" margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid vertical={false} stroke="var(--grade)" />
            <XAxis dataKey="hora" tickFormatter={hora} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "rgb(var(--fraco))" }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "rgb(var(--fraco))" }} />
            <Tooltip content={(props) => <Dica {...props} />} cursor={{ fill: "rgb(var(--elevada))" }} />
            {SERIES.map((serie) => (
              <Bar key={serie.chave} dataKey={serie.chave} name={serie.rotulo} fill={serie.cor} radius={[4, 4, 0, 0]} maxBarSize={18} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
