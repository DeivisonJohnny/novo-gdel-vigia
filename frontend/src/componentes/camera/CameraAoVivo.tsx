import { useEffect, useRef, useState } from "react";
import { Loader2, Maximize2, Minimize2, Users, VideoOff } from "lucide-react";
import type { Camera } from "@/lib/tipos";
import { cn } from "@/lib/cn";
import { Botao } from "../ui/Botao";
import { Selo } from "../ui/Selo";
import { useWebRTC } from "./useWebRTC";
import type { MapaDeteccoes } from "./useDeteccoes";
import { areaDoConteudo, desenharDeteccao } from "./desenho";

const DETECCAO_VALIDA_MS = 3000;
const INTERVALO_QUADRO_MS = 700;
const ROTULO_MODO = { conectando: "Conectando", webrtc: "Tempo real", mjpeg: "Quadros da análise" };

interface Props {
  camera: Camera;
  webrtc: boolean;
  deteccoes: MapaDeteccoes;
  visivel: boolean;
  ampliada?: boolean;
  aoAmpliar?: () => void;
}

export function CameraAoVivo({ camera, webrtc, deteccoes, visivel, ampliada = false, aoAmpliar }: Props) {
  const video = useRef<HTMLVideoElement>(null);
  const imagem = useRef<HTMLImageElement>(null);
  const tela = useRef<HTMLCanvasElement>(null);
  const caixa = useRef<HTMLDivElement>(null);
  const modo = useWebRTC(camera.nome, webrtc && camera.online, video);
  const [pessoas, setPessoas] = useState(camera.pessoas);
  const [versaoQuadro, setVersaoQuadro] = useState(0);
  const mostrarQuadros = camera.online && visivel && modo === "mjpeg";

  useEffect(() => {
    if (!mostrarQuadros) return;
    const relogio = setInterval(() => setVersaoQuadro((versao) => versao + 1), INTERVALO_QUADRO_MS);
    return () => clearInterval(relogio);
  }, [mostrarQuadros]);

  useEffect(() => {
    let quadro = 0;
    const pintar = () => {
      quadro = requestAnimationFrame(pintar);
      const canvas = tela.current;
      const conteiner = caixa.current;
      if (!canvas || !conteiner) return;
      const { clientWidth: largura, clientHeight: altura } = conteiner;
      const densidade = window.devicePixelRatio || 1;
      if (canvas.width !== largura * densidade || canvas.height !== altura * densidade) {
        canvas.width = largura * densidade;
        canvas.height = altura * densidade;
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(densidade, 0, 0, densidade, 0, 0);
      ctx.clearRect(0, 0, largura, altura);
      const atual = deteccoes.current.get(camera.nome);
      if (!atual || performance.now() - atual.recebidaEm > DETECCAO_VALIDA_MS) return;
      const origem = modo === "webrtc" ? video.current : imagem.current;
      const larguraOrigem = origem instanceof HTMLVideoElement ? origem.videoWidth : origem?.naturalWidth ?? 0;
      const alturaOrigem = origem instanceof HTMLVideoElement ? origem.videoHeight : origem?.naturalHeight ?? 0;
      desenharDeteccao(ctx, areaDoConteudo(largura, altura, larguraOrigem, alturaOrigem), atual.deteccao);
    };
    pintar();
    const contador = setInterval(() => setPessoas(deteccoes.current.get(camera.nome)?.deteccao.pessoas.length ?? camera.pessoas), 1000);
    return () => {
      cancelAnimationFrame(quadro);
      clearInterval(contador);
    };
  }, [deteccoes, modo, camera.nome, camera.pessoas]);

  return (
    <article className={cn("group flex flex-col overflow-hidden rounded-xl border bg-superficie shadow-cartao", ampliada && "h-full")}>
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <span className={cn("h-2 w-2 shrink-0 rounded-full", camera.online ? "bg-sucesso" : "bg-alerta")} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{camera.descricao}</p>
          <p className="truncate text-[11px] text-fraco">{camera.loja_nome}</p>
        </div>
        {camera.online && (
          <span className="hidden items-center gap-1 text-xs text-suave sm:flex" title="Pessoas na imagem">
            <Users className="h-3.5 w-3.5" />
            {pessoas}
          </span>
        )}
        {camera.online && <Selo tom={modo === "webrtc" ? "sucesso" : "neutro"}>{ROTULO_MODO[modo]}</Selo>}
        {aoAmpliar && (
          <Botao variante="fantasma" tamanho="sm" onClick={aoAmpliar} aria-label={ampliada ? "Reduzir" : "Ampliar"}>
            {ampliada ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Botao>
        )}
      </header>
      <div ref={caixa} className={cn("relative bg-black", ampliada ? "flex-1" : "aspect-video")}>
        {camera.online ? (
          <>
            <video ref={video} autoPlay muted playsInline className={cn("absolute inset-0 h-full w-full object-contain", modo !== "webrtc" && "invisible")} />
            {mostrarQuadros && (
              <img
                ref={imagem}
                src={`/api/cameras/${encodeURIComponent(camera.nome)}/quadro?v=${versaoQuadro}`}
                alt={camera.descricao}
                className="absolute inset-0 h-full w-full object-contain"
              />
            )}
            {modo === "conectando" && (
              <div className="absolute inset-0 flex items-center justify-center text-white/70">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
            )}
            <canvas ref={tela} className="pointer-events-none absolute inset-0 h-full w-full" />
            <div className="pointer-events-none absolute bottom-2 left-2 flex gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
              <Selo className="bg-black/60 text-white ring-white/10">{camera.fps.toFixed(1)} fps análise</Selo>
              <Selo className="bg-black/60 text-white ring-white/10">
                {camera.cobre_totem ? "vê o totem" : "totem fora da câmera"}
              </Selo>
            </div>
          </>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/70">
            <VideoOff className="h-6 w-6" />
            <p className="text-xs">{camera.erro || "Sem sinal"}</p>
          </div>
        )}
      </div>
    </article>
  );
}
