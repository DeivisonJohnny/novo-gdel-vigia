import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Eye, EyeOff, LayoutGrid } from "lucide-react";
import { api } from "@/lib/api";
import type { Camera, EventoCamera } from "@/lib/tipos";
import { formatarHora } from "@/lib/formato";
import { cn } from "@/lib/cn";
import { useLojaSelecionada } from "@/hooks/useLojaSelecionada";
import { useEventos } from "@/hooks/useEventos";
import { usePaginaVisivel } from "@/hooks/usePaginaVisivel";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Botao } from "@/componentes/ui/Botao";
import { Cartao, CabecalhoCartao } from "@/componentes/ui/Cartao";
import { Segmentado } from "@/componentes/ui/Controles";
import { EstadoVazio, Esqueleto } from "@/componentes/ui/Estados";
import { CameraAoVivo } from "@/componentes/camera/CameraAoVivo";
import { useDeteccoes } from "@/componentes/camera/useDeteccoes";

type Colunas = "1" | "2" | "3";

const GRADE: Record<Colunas, string> = { "1": "grid-cols-1", "2": "md:grid-cols-2", "3": "md:grid-cols-2 2xl:grid-cols-3" };
const COR_EVENTO: Record<EventoCamera["tipo"], string> = {
  pegou: "bg-atencao",
  totem: "bg-sucesso",
  entrou: "bg-info",
  saiu: "bg-fraco",
  objeto: "bg-fraco",
  totem_aprendido: "bg-sucesso",
};

function FeedEventos({ eventos }: { eventos: EventoCamera[] }) {
  return (
    <Cartao className="flex max-h-[calc(100vh-11rem)] flex-col">
      <CabecalhoCartao titulo="Eventos ao vivo" descricao="O que a detecção está vendo agora" />
      {!eventos.length && <EstadoVazio titulo="Aguardando movimento" icone={<Activity className="h-5 w-5" />} />}
      <ol className="rolagem flex-1 overflow-y-auto">
        {eventos.map((evento, indice) => (
          <li key={`${evento.t}-${indice}`} className="flex gap-3 border-b px-4 py-2.5 last:border-0">
            <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", COR_EVENTO[evento.tipo])} />
            <div className="min-w-0 text-xs">
              <p className={cn("text-sm", evento.tipo === "objeto" ? "text-suave" : "text-texto")}>{evento.texto}</p>
              <p className="text-fraco">
                {formatarHora(evento.t)} · {evento.camera}
                {evento.pessoa ? ` · pessoa #${evento.pessoa}` : ""}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </Cartao>
  );
}

export function AoVivo() {
  const { loja } = useLojaSelecionada();
  const { eventosCamera } = useEventos();
  const [colunas, setColunas] = useState<Colunas>("2");
  const [sobreposicao, setSobreposicao] = useState(true);
  const [ampliada, setAmpliada] = useState<string | null>(null);
  const visivel = usePaginaVisivel();
  const { data, isLoading } = useQuery({
    queryKey: ["cameras"],
    queryFn: () => api<{ webrtc: boolean; cameras: Camera[] }>("/api/cameras"),
    refetchInterval: 5_000,
  });

  const cameras = (data?.cameras ?? []).filter((c) => !loja || c.loja === loja);
  const visiveis = ampliada ? cameras.filter((c) => c.nome === ampliada) : cameras;
  const eventos = eventosCamera.filter((e) => !loja || e.loja === loja);
  const deteccoes = useDeteccoes(visiveis.filter((c) => c.online).map((c) => c.nome), sobreposicao && visivel);

  return (
    <>
      <CabecalhoPagina
        titulo="Ao vivo"
        descricao="Vídeo das câmeras com o que a IA detecta desenhado por cima"
        acoes={
          <>
            <Botao tamanho="sm" variante={sobreposicao ? "primaria" : "secundaria"} onClick={() => setSobreposicao(!sobreposicao)}>
              {sobreposicao ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              Detecções
            </Botao>
            <Segmentado
              valor={colunas}
              aoMudar={setColunas}
              opcoes={[
                { valor: "1", rotulo: "1" },
                { valor: "2", rotulo: "2" },
                { valor: "3", rotulo: <LayoutGrid className="h-3.5 w-3.5" /> },
              ]}
            />
          </>
        }
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <div className={cn("grid gap-4", ampliada ? "h-[calc(100vh-11rem)] grid-cols-1" : GRADE[colunas])}>
          {isLoading && Array.from({ length: 2 }, (_, i) => <Esqueleto key={i} className="aspect-video rounded-xl" />)}
          {data && !cameras.length && (
            <Cartao className="col-span-full">
              <EstadoVazio titulo="Nenhuma câmera nesta seleção" descricao="Confira se a detecção está rodando em Sistema." />
            </Cartao>
          )}
          {visiveis.map((camera) => (
            <CameraAoVivo
              key={camera.nome}
              camera={camera}
              webrtc={Boolean(data?.webrtc)}
              deteccoes={deteccoes}
              visivel={visivel}
              ampliada={ampliada === camera.nome}
              aoAmpliar={() => setAmpliada(ampliada === camera.nome ? null : camera.nome)}
            />
          ))}
        </div>
        <FeedEventos eventos={eventos} />
      </div>
      <p className="mt-4 text-xs text-fraco">
        Legenda: caixa cinza = pessoa · laranja = pegou produto · verde = passou no totem · magenta = produto na mão · área tracejada = totem
        aprendido.
      </p>
    </>
  );
}
