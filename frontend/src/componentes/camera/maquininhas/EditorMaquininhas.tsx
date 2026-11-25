import { useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, EyeOff, LocateFixed, RotateCcw, Save, Sparkles, Trash2, UserCheck, type LucideIcon } from "lucide-react";
import { api, enviar } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Caixa, CameraCadastro, MarcacaoMaquininhas } from "@/lib/tipos";
import { Botao } from "../../ui/Botao";
import { EstadoErro, LinhasCarregando } from "../../ui/Estados";
import { MAX_MAQUININHAS, mesmaMarcacao } from "./geometria";
import { QuadroMaquininhas } from "./QuadroMaquininhas";
import { useVista } from "./useVista";

const ATALHOS: [string, string][] = [
  ["Arrastar", "marca uma maquininha"],
  ["Roda do mouse", "zoom no ponto"],
  ["Espaço + arrastar", "move a imagem"],
  ["D / M", "desenhar / mover"],
  ["+ / − / 0", "zoom e imagem inteira"],
  ["Delete", "apaga a selecionada"],
];

const tamanhoEmPorcento = ([x1, y1, x2, y2]: Caixa) => `${Math.round((x2 - x1) * 100)}% × ${Math.round((y2 - y1) * 100)}%`;

function Tecla({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-borda bg-elevada px-1.5 py-0.5 font-sans text-[10px] font-medium text-texto">{children}</kbd>;
}

type Origem = MarcacaoMaquininhas["origem"];

const SITUACOES: Record<Origem, { icone: LucideIcon; titulo: string; texto: string; classe: string }> = {
  manual: {
    icone: UserCheck,
    titulo: "Usando a marcação manual",
    texto: "O aprendizado da IA está parado nesta câmera.",
    classe: "bg-sucesso/10 text-sucesso",
  },
  sem_maquininha: {
    icone: EyeOff,
    titulo: "Esta câmera não mostra a maquininha",
    texto: "O Vigia não considera o totem nesta câmera e a IA não tenta mais encontrar a maquininha nela.",
    classe: "bg-atencao/10 text-atencao",
  },
  automatica: {
    icone: Bot,
    titulo: "Usando a identificação automática",
    texto: "A IA procura a maquininha sozinha até alguém marcar.",
    classe: "bg-elevada text-suave",
  },
};

function SituacaoAtual({ origem }: { origem: Origem }) {
  const { icone: Icone, titulo, texto, classe } = SITUACOES[origem];
  return (
    <div className={cn("flex gap-2.5 rounded-lg p-3 text-xs", classe)}>
      <Icone className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        <span className="block font-semibold">{titulo}</span>
        {texto}
      </p>
    </div>
  );
}

function ListaDeMaquininhas({ caixas, selecionada, aoSelecionar, aoFocar, aoRemover }: {
  caixas: Caixa[];
  selecionada: number | null;
  aoSelecionar: (indice: number) => void;
  aoFocar: (indice: number) => void;
  aoRemover: (indice: number) => void;
}) {
  if (!caixas.length) {
    return <p className="rounded-lg border border-dashed px-3 py-5 text-center text-xs text-fraco">Nenhuma maquininha marcada ainda</p>;
  }
  return (
    <ul className="space-y-1">
      {caixas.map((caixa, indice) => (
        <li key={indice}>
          <div
            className={cn(
              "group flex items-center gap-2 rounded-lg border px-2 py-1.5 transition-colors",
              selecionada === indice ? "border-sucesso/60 bg-sucesso/10" : "border-transparent hover:bg-elevada",
            )}
          >
            <button type="button" onClick={() => aoSelecionar(indice)} className="foco flex min-w-0 flex-1 items-center gap-2 rounded text-left">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-sucesso text-[11px] font-semibold text-black">{indice + 1}</span>
              <span className="min-w-0">
                <span className="block text-sm font-medium">Maquininha {indice + 1}</span>
                <span className="block text-[11px] tabular-nums text-fraco">{tamanhoEmPorcento(caixa)} da imagem</span>
              </span>
            </button>
            <Botao type="button" tamanho="sm" variante="fantasma" className="h-7 px-2" onClick={() => aoFocar(indice)} aria-label={`Dar zoom na maquininha ${indice + 1}`} title="Dar zoom nesta maquininha">
              <LocateFixed className="h-3.5 w-3.5" />
            </Botao>
            <Botao type="button" tamanho="sm" variante="fantasma" className="h-7 px-2 hover:text-alerta" onClick={() => aoRemover(indice)} aria-label={`Remover maquininha ${indice + 1}`} title="Remover">
              <Trash2 className="h-3.5 w-3.5" />
            </Botao>
          </div>
        </li>
      ))}
    </ul>
  );
}

function FormularioMaquininhas({ camera, marcacao, aoFechar }: {
  camera: CameraCadastro;
  marcacao: MarcacaoMaquininhas;
  aoFechar: () => void;
}) {
  const { automatica } = marcacao;
  const salvas = marcacao.manual ?? [];
  const [caixas, setCaixas] = useState<Caixa[]>(salvas);
  const [selecionada, setSelecionada] = useState<number | null>(null);
  const controle = useVista();
  const caminho = `/api/cameras/${encodeURIComponent(camera.nome)}/maquininhas`;
  const alterada = !mesmaMarcacao(caixas, salvas);

  const salvar = useMutation({
    mutationFn: () => enviar<MarcacaoMaquininhas>(caminho, "PUT", { caixas }),
    onSuccess: () => {
      toast.success(`Maquininha de ${camera.descricao} salva: o Vigia passa a usar esta marcação`);
      aoFechar();
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  const semMaquininha = useMutation({
    mutationFn: () => enviar<MarcacaoMaquininhas>(`${caminho}/ausente`, "PUT"),
    onSuccess: () => {
      toast.success(`${camera.descricao} não vai mais considerar a maquininha`);
      aoFechar();
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  const voltarAoAutomatico = useMutation({
    mutationFn: () => enviar<MarcacaoMaquininhas>(caminho, "DELETE"),
    onSuccess: () => {
      toast.success(`${camera.descricao} voltou a identificar a maquininha sozinha`);
      aoFechar();
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  const ocupado = salvar.isPending || voltarAoAutomatico.isPending || semMaquininha.isPending;

  const remover = (indice: number) => {
    setCaixas((atuais) => atuais.filter((_, posicaoAtual) => posicaoAtual !== indice));
    setSelecionada(null);
  };
  const focar = (indice: number) => {
    setSelecionada(indice);
    controle.focar(caixas[indice]);
  };
  const confirmarSemMaquininha = () => {
    if (window.confirm("Confirmar que a maquininha não aparece nesta câmera? A posição que a IA encontrou será descartada e ela não tentará mais encontrar a maquininha aqui.")) {
      semMaquininha.mutate();
    }
  };
  const confirmarVoltaAoAutomatico = () => {
    if (window.confirm("Apagar a marcação e deixar a IA identificar a maquininha sozinha?")) voltarAoAutomatico.mutate();
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <QuadroMaquininhas
          camera={camera.nome}
          caixas={caixas}
          automatica={automatica}
          selecionada={selecionada}
          controle={controle}
          aoMudar={setCaixas}
          aoSelecionar={setSelecionada}
        />
        <aside className="flex flex-col gap-4">
          <SituacaoAtual origem={marcacao.origem} />
          <section className="space-y-2">
            <header className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Maquininhas</h3>
              <span className="text-xs tabular-nums text-fraco">
                {caixas.length} de {MAX_MAQUININHAS}
              </span>
            </header>
            <ListaDeMaquininhas
              caixas={caixas}
              selecionada={selecionada}
              aoSelecionar={setSelecionada}
              aoFocar={focar}
              aoRemover={remover}
            />
            {automatica && !caixas.length && (
              <Botao type="button" tamanho="sm" className="w-full" onClick={() => setCaixas([automatica])}>
                <Sparkles className="h-3.5 w-3.5" /> Começar pela área que a IA detectou
              </Botao>
            )}
          </section>
          {marcacao.origem !== "sem_maquininha" && (
            <section className="space-y-1.5 rounded-lg border border-dashed p-3">
              <p className="text-xs text-suave">A IA marcou algo que não é a maquininha, ou ela não aparece nesta câmera?</p>
              <Botao type="button" tamanho="sm" className="w-full" onClick={confirmarSemMaquininha} disabled={ocupado}>
                <EyeOff className="h-3.5 w-3.5" /> Não aparece nesta câmera
              </Botao>
            </section>
          )}
          <section className="mt-auto space-y-1.5 border-t pt-3">
            <h3 className="text-xs font-semibold text-suave">Atalhos</h3>
            <dl className="grid grid-cols-[auto_1fr] items-center gap-x-2 gap-y-1 text-[11px] text-suave">
              {ATALHOS.map(([tecla, acao]) => (
                <div key={tecla} className="contents">
                  <dt>
                    <Tecla>{tecla}</Tecla>
                  </dt>
                  <dd>{acao}</dd>
                </div>
              ))}
            </dl>
          </section>
        </aside>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-2 border-t pt-4">
        <div>
          {marcacao.origem !== "automatica" && (
            <Botao type="button" variante="fantasma" onClick={confirmarVoltaAoAutomatico} disabled={ocupado}>
              <RotateCcw className="h-4 w-4" /> Voltar ao automático
            </Botao>
          )}
        </div>
        <div className="flex items-center gap-2">
          {alterada && <span className="text-xs text-atencao">Alterações não salvas</span>}
          <Botao type="button" variante="fantasma" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="button" variante="primaria" onClick={() => salvar.mutate()} disabled={!caixas.length || !alterada || ocupado}>
            <Save className="h-4 w-4" /> {salvar.isPending ? "Salvando…" : "Salvar marcação"}
          </Botao>
        </div>
      </footer>
    </div>
  );
}

export function EditorMaquininhas({ camera, aoFechar }: { camera: CameraCadastro; aoFechar: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["maquininhas", camera.nome],
    queryFn: () => api<MarcacaoMaquininhas>(`/api/cameras/${encodeURIComponent(camera.nome)}/maquininhas`),
    gcTime: 0,
  });
  if (isLoading) return <LinhasCarregando linhas={4} />;
  if (error) return <EstadoErro mensagem={error.message} />;
  return data ? <FormularioMaquininhas camera={camera} marcacao={data} aoFechar={aoFechar} /> : null;
}
