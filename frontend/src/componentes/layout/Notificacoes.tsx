import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, BellOff, Volume2, VolumeX } from "lucide-react";
import { useEventos } from "@/hooks/useEventos";
import { haQuantoTempo } from "@/lib/formato";
import { ROTULO_NIVEL } from "@/lib/rotulos";
import { cn } from "@/lib/cn";
import { Botao } from "../ui/Botao";

export function Notificacoes() {
  const { notificacoes, naoLidas, marcarLidas, som, alternarSom } = useEventos();
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;
    const fora = (evento: MouseEvent) => caixa.current && !caixa.current.contains(evento.target as Node) && setAberto(false);
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, [aberto]);

  const alternar = () => {
    setAberto(!aberto);
    marcarLidas();
  };

  return (
    <div className="flex items-center gap-1">
      <Botao variante="fantasma" tamanho="sm" onClick={alternarSom} aria-label={som ? "Silenciar avisos" : "Ativar som dos avisos"} title={som ? "Som ligado" : "Som desligado"}>
        {som ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
      </Botao>
      <div className="relative" ref={caixa}>
        <Botao variante="fantasma" tamanho="sm" onClick={alternar} aria-label="Avisos" className="relative">
          {notificacoes.length ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
          {naoLidas > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-alerta px-1 text-[10px] font-semibold text-white">
              {naoLidas}
            </span>
          )}
        </Botao>
        {aberto && (
          <div className="absolute right-0 top-10 z-40 w-80 animate-entrar overflow-hidden rounded-xl border bg-superficie shadow-2xl">
            <header className="border-b px-4 py-3 text-sm font-semibold">Avisos desta sessão</header>
            <ul className="rolagem max-h-96 overflow-y-auto">
              {notificacoes.length === 0 && <li className="px-4 py-8 text-center text-xs text-suave">Nenhum aviso ainda.</li>}
              {notificacoes.map(({ id, t, dados }) => (
                <li key={id}>
                  <Link to={`/ocorrencias/${dados.id}`} onClick={() => setAberto(false)} className="flex gap-3 border-b px-4 py-3 hover:bg-elevada">
                    <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", dados.nivel === "alerta" ? "bg-alerta" : "bg-atencao")} />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium">
                        {ROTULO_NIVEL[dados.nivel]} · {dados.cameras.join(", ")}
                      </span>
                      <span className="block truncate text-xs text-suave">{dados.motivo}</span>
                      <span className="block text-[11px] text-fraco">{haQuantoTempo(t)}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
