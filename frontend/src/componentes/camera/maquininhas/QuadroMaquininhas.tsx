import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { Hand, ImageOff, Maximize, RefreshCw, SquareDashed, ZoomIn, ZoomOut } from "lucide-react";
import type { Caixa } from "@/lib/tipos";
import { cn } from "@/lib/cn";
import {
  CANTOS,
  MAX_MAQUININHAS,
  caixaEntre,
  cantoValido,
  limitar,
  moverCaixa,
  posicao,
  redimensionarCaixa,
  temTamanho,
  type Canto,
  type Ponto,
} from "./geometria";
import { ESCALA_MAXIMA, type ControleDaVista } from "./useVista";

type Ferramenta = "desenhar" | "mover";

type Gesto =
  | { tipo: "desenhando"; inicio: Ponto }
  | { tipo: "movendo"; indice: number; origem: Ponto; caixaInicial: Caixa }
  | { tipo: "redimensionando"; indice: number; canto: Canto; caixaInicial: Caixa }
  | { tipo: "arrastando-imagem"; origem: Ponto; deslocamentoInicial: Ponto };

const BORDA_PX = 2;
const ALCA_PX = 11;
const GUIA_PX = 1;
const BOTAO_DO_MEIO = 1;

const ALCAS: Record<Canto, { classe: string; transform: string }> = {
  no: { classe: "left-0 top-0 cursor-nwse-resize", transform: "translate(-50%, -50%)" },
  ne: { classe: "right-0 top-0 cursor-nesw-resize", transform: "translate(50%, -50%)" },
  so: { classe: "left-0 bottom-0 cursor-nesw-resize", transform: "translate(-50%, 50%)" },
  se: { classe: "right-0 bottom-0 cursor-nwse-resize", transform: "translate(50%, 50%)" },
};

const TECLAS_DE_ZOOM: Record<string, keyof Pick<ControleDaVista, "aumentar" | "diminuir" | "verInteira">> = {
  "+": "aumentar",
  "=": "aumentar",
  "-": "diminuir",
  "0": "verInteira",
};

const elementoDe = (alvo: EventTarget) => (alvo instanceof Element ? alvo : null);

const digitando = (alvo: EventTarget | null) =>
  alvo instanceof HTMLInputElement || alvo instanceof HTMLTextAreaElement || alvo instanceof HTMLSelectElement;

function BotaoDaBarra({ titulo, ativo, children, ...props }: { titulo: string; ativo?: boolean; children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      title={titulo}
      aria-label={titulo}
      aria-pressed={ativo}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md transition-colors disabled:opacity-35",
        ativo ? "bg-white text-black" : "text-white/85 hover:bg-white/15 hover:text-white",
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function Retangulo({ caixa, indice, selecionada, editavel, escala }: {
  caixa: Caixa;
  indice: number;
  selecionada: boolean;
  editavel: boolean;
  escala: number;
}) {
  return (
    <div
      data-indice={indice}
      className={cn(
        "absolute border-solid transition-colors",
        selecionada ? "border-white bg-sucesso/30" : "border-sucesso bg-sucesso/15 hover:bg-sucesso/25",
        editavel && "cursor-move",
      )}
      style={{ ...posicao(caixa), borderWidth: BORDA_PX / escala, boxShadow: selecionada ? `0 0 0 ${BORDA_PX / escala}px rgb(34 197 94)` : undefined }}
    >
      <span
        className={cn(
          "absolute bottom-full left-0 origin-bottom-left whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold leading-none",
          selecionada ? "bg-white text-black" : "bg-sucesso text-black",
        )}
        style={{ transform: `translateY(${-3 / escala}px) scale(${1 / escala})` }}
      >
        {indice + 1}
      </span>
      {selecionada &&
        editavel &&
        CANTOS.map((canto) => (
          <span
            key={canto}
            data-alca={canto}
            className={cn("absolute rounded-full border-sucesso bg-white shadow", ALCAS[canto].classe)}
            style={{ width: ALCA_PX / escala, height: ALCA_PX / escala, borderWidth: BORDA_PX / escala, transform: ALCAS[canto].transform }}
          />
        ))}
    </div>
  );
}

function Guias({ ponto, escala }: { ponto: Ponto; escala: number }) {
  return (
    <>
      <div className="pointer-events-none absolute inset-y-0 bg-white/60 mix-blend-difference" style={{ left: `${ponto.x * 100}%`, width: GUIA_PX / escala }} />
      <div className="pointer-events-none absolute inset-x-0 bg-white/60 mix-blend-difference" style={{ top: `${ponto.y * 100}%`, height: GUIA_PX / escala }} />
    </>
  );
}

function Minimapa({ src, controle, caixas }: { src: string; controle: ControleDaVista; caixas: Caixa[] }) {
  const { vista, janela } = controle;
  const largura = janela.current?.clientWidth || 1;
  const altura = janela.current?.clientHeight || 1;
  const visivel: Caixa = [
    -vista.x / (largura * vista.escala),
    -vista.y / (altura * vista.escala),
    (-vista.x + largura) / (largura * vista.escala),
    (-vista.y + altura) / (altura * vista.escala),
  ];
  return (
    <div className="pointer-events-none absolute bottom-2 right-2 w-36 overflow-hidden rounded-md border border-white/30 bg-black shadow-lg">
      <img src={src} alt="" className="block w-full opacity-70" />
      {caixas.map((caixa, indice) => (
        <div key={indice} className="absolute bg-sucesso/70" style={posicao(caixa)} />
      ))}
      <div className="absolute border-2 border-white" style={posicao(visivel)} />
    </div>
  );
}

export function QuadroMaquininhas({ camera, caixas, automatica, selecionada, controle, aoMudar, aoSelecionar }: {
  camera: string;
  caixas: Caixa[];
  automatica: Caixa | null;
  selecionada: number | null;
  controle: ControleDaVista;
  aoMudar: (caixas: Caixa[]) => void;
  aoSelecionar: (indice: number | null) => void;
}) {
  const { janela, vista } = controle;
  const palco = useRef<HTMLDivElement>(null);
  const [versao, setVersao] = useState(() => Date.now());
  const [semImagem, setSemImagem] = useState(false);
  const [ferramenta, setFerramenta] = useState<Ferramenta>("desenhar");
  const [espacoPressionado, setEspacoPressionado] = useState(false);
  const [gesto, setGesto] = useState<Gesto | null>(null);
  const [rascunho, setRascunho] = useState<Caixa | null>(null);
  const [cursor, setCursor] = useState<Ponto | null>(null);
  const cheio = caixas.length >= MAX_MAQUININHAS;
  const ferramentaAtiva: Ferramenta = espacoPressionado ? "mover" : ferramenta;
  const desenhando = ferramentaAtiva === "desenhar";
  const src = `/api/cameras/${encodeURIComponent(camera)}/quadro?v=${versao}`;

  const removerSelecionada = () => {
    if (selecionada === null) return;
    aoMudar(caixas.filter((_, indice) => indice !== selecionada));
    aoSelecionar(null);
  };

  useEffect(() => {
    const pressionar = (evento: KeyboardEvent) => {
      if (digitando(evento.target)) return;
      if (evento.key === " " && !(evento.target instanceof HTMLButtonElement)) {
        evento.preventDefault();
        setEspacoPressionado(true);
        return;
      }
      const acaoDeZoom = TECLAS_DE_ZOOM[evento.key];
      if (acaoDeZoom) controle[acaoDeZoom]();
      else if (evento.key.toLowerCase() === "d") setFerramenta("desenhar");
      else if (["m", "h"].includes(evento.key.toLowerCase())) setFerramenta("mover");
      else if (evento.key === "Delete" || evento.key === "Backspace") {
        evento.preventDefault();
        removerSelecionada();
      }
    };
    const soltar = (evento: KeyboardEvent) => evento.key === " " && setEspacoPressionado(false);
    window.addEventListener("keydown", pressionar);
    window.addEventListener("keyup", soltar);
    return () => {
      window.removeEventListener("keydown", pressionar);
      window.removeEventListener("keyup", soltar);
    };
  });

  const pontoNaImagem = (evento: PointerEvent): Ponto => {
    const limites = palco.current?.getBoundingClientRect();
    if (!limites) return { x: 0, y: 0 };
    return { x: limitar((evento.clientX - limites.left) / limites.width), y: limitar((evento.clientY - limites.top) / limites.height) };
  };

  const trocarCaixa = (indice: number, caixa: Caixa) => aoMudar(caixas.map((atual, posicaoAtual) => (posicaoAtual === indice ? caixa : atual)));

  const comecar = (evento: PointerEvent<HTMLDivElement>) => {
    if (semImagem || (evento.button !== 0 && evento.button !== BOTAO_DO_MEIO)) return;
    evento.currentTarget.setPointerCapture(evento.pointerId);
    const alvo = elementoDe(evento.target);
    const elementoDaCaixa = alvo?.closest<HTMLElement>("[data-indice]");
    const indice = elementoDaCaixa ? Number(elementoDaCaixa.dataset.indice) : null;
    const canto = cantoValido(alvo?.closest<HTMLElement>("[data-alca]")?.dataset.alca);
    const ponto = pontoNaImagem(evento);

    if (evento.button === BOTAO_DO_MEIO || !desenhando) {
      setGesto({ tipo: "arrastando-imagem", origem: { x: evento.clientX, y: evento.clientY }, deslocamentoInicial: { x: vista.x, y: vista.y } });
      return;
    }
    if (indice !== null && canto) {
      setGesto({ tipo: "redimensionando", indice, canto, caixaInicial: caixas[indice] });
      return;
    }
    if (indice !== null) {
      aoSelecionar(indice);
      setGesto({ tipo: "movendo", indice, origem: ponto, caixaInicial: caixas[indice] });
      return;
    }
    aoSelecionar(null);
    if (!cheio) setGesto({ tipo: "desenhando", inicio: ponto });
  };

  const mover = (evento: PointerEvent<HTMLDivElement>) => {
    const ponto = pontoNaImagem(evento);
    setCursor(ponto);
    if (!gesto) return;
    if (gesto.tipo === "desenhando") setRascunho(caixaEntre(gesto.inicio, ponto));
    if (gesto.tipo === "movendo") trocarCaixa(gesto.indice, moverCaixa(gesto.caixaInicial, { x: ponto.x - gesto.origem.x, y: ponto.y - gesto.origem.y }));
    if (gesto.tipo === "redimensionando") trocarCaixa(gesto.indice, redimensionarCaixa(gesto.caixaInicial, gesto.canto, ponto));
    if (gesto.tipo === "arrastando-imagem")
      controle.deslocarPara(gesto.deslocamentoInicial.x + evento.clientX - gesto.origem.x, gesto.deslocamentoInicial.y + evento.clientY - gesto.origem.y);
  };

  const terminar = () => {
    if (gesto?.tipo === "desenhando" && rascunho && temTamanho(rascunho)) {
      aoMudar([...caixas, rascunho]);
      aoSelecionar(caixas.length);
    }
    if (gesto?.tipo === "redimensionando" && !temTamanho(caixas[gesto.indice])) trocarCaixa(gesto.indice, gesto.caixaInicial);
    setGesto(null);
    setRascunho(null);
  };

  const recarregar = () => {
    setSemImagem(false);
    setVersao(Date.now());
  };

  const cursorDaJanela = semImagem ? "default" : !desenhando ? (gesto ? "grabbing" : "grab") : cheio ? "default" : "crosshair";
  const mostrarGuias = desenhando && !cheio && cursor && (!gesto || gesto.tipo === "desenhando");

  return (
    <div
      ref={janela}
      onPointerDown={comecar}
      onPointerMove={mover}
      onPointerUp={terminar}
      onPointerCancel={terminar}
      onPointerLeave={() => setCursor(null)}
      onAuxClick={(evento) => evento.preventDefault()}
      className="relative touch-none select-none overflow-hidden rounded-lg bg-black ring-1 ring-borda"
      style={{ cursor: cursorDaJanela }}
    >
      <div
        ref={palco}
        className={cn("relative origin-top-left", !gesto && "transition-transform duration-150 ease-out")}
        style={{ transform: `translate(${vista.x}px, ${vista.y}px) scale(${vista.escala})` }}
      >
        {semImagem ? (
          <div className="flex aspect-video flex-col items-center justify-center gap-2 text-white/70">
            <ImageOff className="h-6 w-6" />
            <p className="text-sm">A câmera ainda não mandou imagem</p>
            <p className="text-xs text-white/50">Confira se ela está online e clique em atualizar</p>
          </div>
        ) : (
          <img src={src} alt="Imagem atual da câmera" draggable={false} onError={() => setSemImagem(true)} className="block w-full" />
        )}
        {automatica && !caixas.length && !semImagem && (
          <div className="pointer-events-none absolute border-dashed border-white/80" style={{ ...posicao(automatica), borderWidth: BORDA_PX / vista.escala }}>
            <span
              className="absolute bottom-full left-0 origin-bottom-left whitespace-nowrap rounded bg-black/75 px-1.5 py-0.5 text-[11px] leading-none text-white"
              style={{ transform: `translateY(${-3 / vista.escala}px) scale(${1 / vista.escala})` }}
            >
              detectada pela IA
            </span>
          </div>
        )}
        {caixas.map((caixa, indice) => (
          <Retangulo key={indice} caixa={caixa} indice={indice} selecionada={selecionada === indice} editavel={desenhando} escala={vista.escala} />
        ))}
        {rascunho && (
          <div className="pointer-events-none absolute border-dashed border-white bg-sucesso/20" style={{ ...posicao(rascunho), borderWidth: BORDA_PX / vista.escala }} />
        )}
        {mostrarGuias && <Guias ponto={cursor} escala={vista.escala} />}
      </div>

      <div onPointerDown={(evento) => evento.stopPropagation()} className="absolute left-2 top-2 flex items-center gap-0.5 rounded-lg bg-black/70 p-1 shadow-lg backdrop-blur" style={{ cursor: "default" }}>
        <BotaoDaBarra titulo="Desenhar e ajustar maquininhas (D)" ativo={ferramentaAtiva === "desenhar"} onClick={() => setFerramenta("desenhar")}>
          <SquareDashed className="h-4 w-4" />
        </BotaoDaBarra>
        <BotaoDaBarra titulo="Arrastar a imagem (M ou segure Espaço)" ativo={ferramentaAtiva === "mover"} onClick={() => setFerramenta("mover")}>
          <Hand className="h-4 w-4" />
        </BotaoDaBarra>
        <span className="mx-1 h-5 w-px bg-white/20" />
        <BotaoDaBarra titulo="Diminuir zoom (−)" onClick={controle.diminuir} disabled={vista.escala <= 1}>
          <ZoomOut className="h-4 w-4" />
        </BotaoDaBarra>
        <button
          type="button"
          title="Ver a imagem inteira (0)"
          onClick={controle.verInteira}
          className="h-8 min-w-12 rounded-md px-1 text-xs font-medium tabular-nums text-white/85 hover:bg-white/15"
        >
          {Math.round(vista.escala * 100)}%
        </button>
        <BotaoDaBarra titulo="Aumentar zoom (+)" onClick={controle.aumentar} disabled={vista.escala >= ESCALA_MAXIMA}>
          <ZoomIn className="h-4 w-4" />
        </BotaoDaBarra>
        <BotaoDaBarra titulo="Ver a imagem inteira (0)" onClick={controle.verInteira} disabled={vista.escala === 1}>
          <Maximize className="h-4 w-4" />
        </BotaoDaBarra>
      </div>

      <div onPointerDown={(evento) => evento.stopPropagation()} className="absolute right-2 top-2 rounded-lg bg-black/70 p-1 shadow-lg backdrop-blur" style={{ cursor: "default" }}>
        <BotaoDaBarra titulo="Buscar imagem nova da câmera" onClick={recarregar}>
          <RefreshCw className="h-4 w-4" />
        </BotaoDaBarra>
      </div>

      {!caixas.length && !gesto && !semImagem && (
        <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
          <span className="rounded-full bg-black/75 px-3 py-1.5 text-xs text-white shadow-lg">
            Clique e arraste sobre a maquininha · role o mouse para dar zoom
          </span>
        </div>
      )}
      {cheio && desenhando && !gesto && (
        <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
          <span className="rounded-full bg-black/75 px-3 py-1.5 text-xs text-white shadow-lg">Limite de {MAX_MAQUININHAS} maquininhas por câmera</span>
        </div>
      )}
      {vista.escala > 1 && !semImagem && <Minimapa src={src} controle={controle} caixas={caixas} />}
    </div>
  );
}
