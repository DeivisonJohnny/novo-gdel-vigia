import { Campo } from "./ui/Controles";

export function Periodo({ desde, ate, aoMudar }: { desde: string; ate: string; aoMudar: (desde: string, ate: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <Campo type="date" value={desde} max={ate || undefined} onChange={(e) => aoMudar(e.target.value, ate)} aria-label="De" className="w-36" />
      <span className="text-xs text-fraco">até</span>
      <Campo type="date" value={ate} min={desde || undefined} onChange={(e) => aoMudar(desde, e.target.value)} aria-label="Até" className="w-36" />
    </div>
  );
}
