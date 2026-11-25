import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import type { EventoCamera, Notificacao } from "@/lib/tipos";
import { ROTULO_NIVEL } from "@/lib/rotulos";

const MAX_EVENTOS_CAMERA = 60;
const MAX_NOTIFICACOES = 30;
const CHAVE_SOM = "vigia:som";
const CONSULTAS_AFETADAS: Record<string, string[][]> = {
  ocorrencia: [["ocorrencias"], ["ocorrencia"], ["painel"], ["visitas"]],
  ocorrencia_triagem: [["ocorrencias"], ["painel"], ["visitas"]],
  ocorrencia_descartada: [["ocorrencias"], ["ocorrencia"], ["painel"]],
  ocorrencia_resolvida: [["ocorrencias"], ["ocorrencia"], ["painel"], ["visitas"]],
  ocorrencia_revisada: [["ocorrencias"], ["ocorrencia"], ["painel"]],
  visita: [["visitas"], ["painel"]],
  clipe: [["ocorrencia"]],
};

interface DadosOcorrencia {
  id: number;
  loja: string | null;
  cameras: string[];
  nivel: "alerta" | "atencao";
  score: number;
  motivo: string;
}

interface Eventos {
  conectado: boolean;
  eventosCamera: EventoCamera[];
  notificacoes: Notificacao<DadosOcorrencia>[];
  naoLidas: number;
  marcarLidas: () => void;
  som: boolean;
  alternarSom: () => void;
}

const ContextoEventos = createContext<Eventos | null>(null);

function tocarAlerta(nivel: string) {
  try {
    const audio = new AudioContext();
    const notas = nivel === "alerta" ? [880, 660, 880] : [660];
    notas.forEach((frequencia, indice) => {
      const oscilador = audio.createOscillator();
      const volume = audio.createGain();
      const inicio = audio.currentTime + indice * 0.18;
      oscilador.frequency.value = frequencia;
      volume.gain.setValueAtTime(0.0001, inicio);
      volume.gain.exponentialRampToValueAtTime(0.15, inicio + 0.02);
      volume.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.16);
      oscilador.connect(volume).connect(audio.destination);
      oscilador.start(inicio);
      oscilador.stop(inicio + 0.17);
    });
  } catch {
    return;
  }
}

function notificarNoSistema(dados: DadosOcorrencia, abrir: (caminho: string) => void) {
  if (!("Notification" in window) || Notification.permission !== "granted" || document.hasFocus()) return;
  const aviso = new Notification(`${ROTULO_NIVEL[dados.nivel]} · ${dados.cameras.join(", ")}`, {
    body: dados.motivo,
    tag: `ocorrencia-${dados.id}`,
    icon: "/icone.svg",
  });
  aviso.onclick = () => {
    window.focus();
    abrir(`/ocorrencias/${dados.id}`);
    aviso.close();
  };
}

function lerSom() {
  try {
    return localStorage.getItem(CHAVE_SOM) !== "0";
  } catch {
    return true;
  }
}

export function ProvedorEventos({ children }: { children: ReactNode }) {
  const cliente = useQueryClient();
  const navegar = useNavigate();
  const navegarRef = useRef(navegar);
  navegarRef.current = navegar;
  const [conectado, setConectado] = useState(false);
  const [eventosCamera, setEventosCamera] = useState<EventoCamera[]>([]);
  const [notificacoes, setNotificacoes] = useState<Notificacao<DadosOcorrencia>[]>([]);
  const [naoLidas, setNaoLidas] = useState(0);
  const [som, setSom] = useState(lerSom);
  const somRef = useRef(som);
  somRef.current = som;

  useEffect(() => {
    const fonte = new EventSource("/api/eventos");
    fonte.onopen = () => setConectado(true);
    fonte.onerror = () => setConectado(false);

    const invalidar = (tipo: string) =>
      (CONSULTAS_AFETADAS[tipo] ?? []).forEach((chave) => cliente.invalidateQueries({ queryKey: chave }));

    const aoOcorrer = (mensagem: MessageEvent) => {
      const notificacao: Notificacao<DadosOcorrencia> = JSON.parse(mensagem.data);
      const dados = notificacao.dados;
      setNotificacoes((anteriores) => [notificacao, ...anteriores].slice(0, MAX_NOTIFICACOES));
      setNaoLidas((n) => n + 1);
      invalidar("ocorrencia");
      if (somRef.current) tocarAlerta(dados.nivel);
      notificarNoSistema(dados, (caminho) => navegarRef.current(caminho));
      const exibir = dados.nivel === "alerta" ? toast.error : toast.warning;
      exibir(`${ROTULO_NIVEL[dados.nivel]} em ${dados.cameras.join(", ")}`, {
        description: dados.motivo,
        duration: 12000,
        action: { label: "Ver", onClick: () => navegarRef.current(`/ocorrencias/${dados.id}`) },
      });
    };

    const aoEventoCamera = (mensagem: MessageEvent) => {
      const evento: EventoCamera = JSON.parse(mensagem.data).dados;
      setEventosCamera((anteriores) => [evento, ...anteriores].slice(0, MAX_EVENTOS_CAMERA));
    };

    fonte.addEventListener("ocorrencia", aoOcorrer);
    fonte.addEventListener("evento_camera", aoEventoCamera);
    ["ocorrencia_triagem", "ocorrencia_descartada", "ocorrencia_resolvida", "ocorrencia_revisada", "visita", "clipe"].forEach((tipo) =>
      fonte.addEventListener(tipo, () => invalidar(tipo)),
    );
    return () => fonte.close();
  }, [cliente]);

  const alternarSom = () => {
    const novo = !som;
    setSom(novo);
    try {
      localStorage.setItem(CHAVE_SOM, novo ? "1" : "0");
    } catch {
      return;
    }
    if (novo && "Notification" in window && Notification.permission === "default") void Notification.requestPermission();
  };

  return (
    <ContextoEventos.Provider
      value={{ conectado, eventosCamera, notificacoes, naoLidas, marcarLidas: () => setNaoLidas(0), som, alternarSom }}
    >
      {children}
    </ContextoEventos.Provider>
  );
}

export function useEventos() {
  const contexto = useContext(ContextoEventos);
  if (!contexto) throw new Error("useEventos fora do ProvedorEventos");
  return contexto;
}
