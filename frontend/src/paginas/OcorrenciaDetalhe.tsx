import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, CircleHelp, DoorOpen, Film, LoaderCircle, ShieldX, Sparkles } from "lucide-react";
import { api, enviar, urlArquivo } from "@/lib/api";
import type { OcorrenciaDetalhe as Detalhe, Veredito } from "@/lib/tipos";
import { formatarDataCompleta, formatarDuracao, formatarHora, formatarMoeda } from "@/lib/formato";
import { ROTULO_VEREDITO, rotuloMetodo } from "@/lib/rotulos";
import { cn } from "@/lib/cn";
import { Botao } from "@/componentes/ui/Botao";
import { Cartao, CabecalhoCartao } from "@/componentes/ui/Cartao";
import { EstadoErro, EstadoVazio, Esqueleto } from "@/componentes/ui/Estados";
import { SeloDoTipo, SeloIA, SeloSituacao, SeloVeredito } from "@/componentes/ui/Selo";
import { BarraScore, ListaMotivos } from "@/componentes/ocorrencias";

const OPCOES_VEREDITO: { valor: Veredito; icone: typeof ShieldX; classe: string }[] = [
  { valor: "furto", icone: ShieldX, classe: "data-[ativo=true]:border-alerta data-[ativo=true]:bg-alerta/10 data-[ativo=true]:text-alerta" },
  { valor: "falso_positivo", icone: CheckCircle2, classe: "data-[ativo=true]:border-sucesso data-[ativo=true]:bg-sucesso/10 data-[ativo=true]:text-sucesso" },
  { valor: "duvida", icone: CircleHelp, classe: "data-[ativo=true]:border-fraco data-[ativo=true]:bg-elevada data-[ativo=true]:text-texto" },
];

const COR_LINHA: Record<string, string> = { entrou: "bg-info", pegou: "bg-atencao", totem: "bg-sucesso", saiu: "bg-fraco" };

function Evidencias({ detalhe }: { detalhe: Detalhe }) {
  const [selecionada, setSelecionada] = useState(0);
  const midias = [...detalhe.clipes.map((c) => ({ tipo: "video" as const, caminho: c })), ...detalhe.evidencias.map((e) => ({ tipo: "foto" as const, caminho: e }))];
  if (!midias.length) return <EstadoVazio titulo="Sem evidências" />;
  const atual = midias[Math.min(selecionada, midias.length - 1)];
  return (
    <div className="space-y-3 p-5">
      <div className="overflow-hidden rounded-lg bg-black">
        {atual.tipo === "video" ? (
          <video key={atual.caminho} src={urlArquivo(atual.caminho)} controls preload="metadata" className="aspect-video w-full" />
        ) : (
          <img src={urlArquivo(atual.caminho)} alt="Evidência" className="aspect-video w-full object-contain" />
        )}
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {midias.map((midia, indice) => (
          <button
            key={midia.caminho}
            onClick={() => setSelecionada(indice)}
            className={cn("foco relative h-16 w-24 shrink-0 overflow-hidden rounded-md border-2", indice === selecionada ? "border-primaria" : "border-transparent opacity-70 hover:opacity-100")}
          >
            {midia.tipo === "video" ? (
              <span className="flex h-full w-full items-center justify-center bg-elevada text-xs text-suave">
                <Film className="mr-1 h-4 w-4" /> vídeo
              </span>
            ) : (
              <img src={urlArquivo(midia.caminho)} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
            )}
          </button>
        ))}
      </div>
      {!detalhe.clipes.length && <p className="text-xs text-fraco">O vídeo da visita aparece aqui quando o roteador terminar de gravar o trecho.</p>}
    </div>
  );
}

function ParecerDaIA({ detalhe }: { detalhe: Detalhe }) {
  const { ia, situacao } = detalhe;
  if (situacao !== "triagem" && !ia) return null;
  const detalhes = ia?.modelo ? `${ia.modelo} · ${ia.imagens ?? 0} imagens` : "Filtro antes da revisão humana";
  return (
    <Cartao>
      <CabecalhoCartao titulo="Triagem da IA" descricao={detalhes} />
      <div className="space-y-3 p-5 text-sm">
        {situacao === "triagem" ? (
          <p className="flex items-center gap-2 text-suave">
            <LoaderCircle className="h-4 w-4 animate-spin" /> Analisando as fotos e o vídeo da visita…
          </p>
        ) : (
          <SeloIA ia={ia} situacao={situacao} />
        )}
        {ia?.resumo && <p>{ia.resumo}</p>}
        {Boolean(ia?.sinais?.length) && (
          <ul className="list-disc space-y-1 pl-4 text-suave">
            {ia?.sinais?.map((sinal) => <li key={sinal}>{sinal}</li>)}
          </ul>
        )}
        {ia?.justificativa && (
          <div className="rounded-lg bg-elevada px-3 py-2">
            <p className="text-xs font-medium text-suave">Justificativa da IA</p>
            <p className="mt-1 whitespace-pre-line">{ia.justificativa}</p>
          </div>
        )}
        {ia?.erro && <p className="text-xs text-alerta">{ia.erro}</p>}
        {situacao === "descartada" && (
          <p className="rounded-lg bg-elevada px-3 py-2 text-xs text-suave">
            Saiu da fila porque a IA viu falso positivo com confiança alta. Se discordar, registre a revisão ao lado.
          </p>
        )}
        <p className="flex items-center gap-1.5 text-xs text-fraco">
          <Sparkles className="h-3.5 w-3.5" /> O parecer ajuda na triagem. A decisão final é do operador.
        </p>
      </div>
    </Cartao>
  );
}

function Revisao({ detalhe }: { detalhe: Detalhe }) {
  const cliente = useQueryClient();
  const [veredito, setVeredito] = useState<Veredito | null>(detalhe.veredito);
  const [observacao, setObservacao] = useState(detalhe.observacao ?? "");
  const salvar = useMutation({
    mutationFn: () => enviar<Detalhe>(`/api/ocorrencias/${detalhe.id}/revisao`, "POST", { veredito, observacao }),
    onSuccess: (atualizada) => {
      cliente.setQueryData(["ocorrencia", String(detalhe.id)], atualizada);
      void cliente.invalidateQueries({ queryKey: ["ocorrencias"] });
      void cliente.invalidateQueries({ queryKey: ["painel"] });
      toast.success("Revisão registrada");
    },
    onError: (erro: Error) => toast.error(erro.message),
  });

  return (
    <Cartao>
      <CabecalhoCartao titulo="Revisão" descricao={detalhe.revisada_por ? `Por ${detalhe.revisada_por}` : "O que aconteceu de fato?"} />
      <div className="space-y-4 p-5">
        <div className="grid gap-2">
          {OPCOES_VEREDITO.map(({ valor, icone: Icone, classe }) => (
            <button
              key={valor}
              data-ativo={veredito === valor}
              onClick={() => setVeredito(valor)}
              className={cn("foco flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm text-suave transition-colors hover:bg-elevada", classe)}
            >
              <Icone className="h-4 w-4" />
              {ROTULO_VEREDITO[valor]}
            </button>
          ))}
        </div>
        <textarea
          value={observacao}
          onChange={(e) => setObservacao(e.target.value)}
          placeholder="Observação (opcional): o que o vídeo mostra, quem foi avisado…"
          rows={3}
          maxLength={2000}
          className="foco w-full resize-none rounded-lg border bg-superficie p-3 text-sm placeholder:text-fraco"
        />
        <Botao variante="primaria" className="w-full" disabled={!veredito || salvar.isPending} onClick={() => salvar.mutate()}>
          {detalhe.veredito ? "Atualizar revisão" : "Registrar revisão"}
        </Botao>
      </div>
    </Cartao>
  );
}

export function OcorrenciaDetalhe() {
  const { id = "" } = useParams();
  const { data, isLoading, error } = useQuery({ queryKey: ["ocorrencia", id], queryFn: () => api<Detalhe>(`/api/ocorrencias/${id}`) });

  return (
    <>
      <Link to="/ocorrencias" className="foco mb-4 inline-flex items-center gap-1.5 rounded text-sm text-suave hover:text-texto">
        <ArrowLeft className="h-4 w-4" /> Ocorrências
      </Link>
      {error && <EstadoErro mensagem={(error as Error).message} />}
      {isLoading && <Esqueleto className="h-96 rounded-xl" />}
      {data && (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold tracking-tight">Ocorrência #{data.id}</h1>
                <SeloDoTipo ocorrencia={data} />
                {data.veredito ? <SeloVeredito veredito={data.veredito} /> : <SeloSituacao situacao={data.situacao} />}
              </div>
              <p className="mt-1 text-sm text-suave">
                {data.loja_nome} · {data.cameras.join(", ")} · {formatarDataCompleta(data.inicio)}
              </p>
            </div>
            {data.tipo === "suspeita" && (
              <div className="text-right">
                <p className="text-xs text-suave">Score de suspeita</p>
                <BarraScore score={data.score} />
              </div>
            )}
          </div>
          {data.tipo === "sem_compra" && (
            <div className="mb-6 flex items-center gap-2 rounded-lg border border-revisao/30 bg-revisao/5 px-4 py-3 text-sm text-revisao">
              <DoorOpen className="h-4 w-4 shrink-0" />
              <span>
                Entrou às {formatarHora(data.inicio)} e saiu às {formatarHora(data.fim)} ({formatarDuracao(data.fim - data.inicio)} na loja), sem nenhuma
                compra na TouchPay. O vídeo traz todas as câmeras da loja no período: assista e registre o que viu.
              </span>
            </div>
          )}
          {data.resolucao && (
            <div className="mb-6 flex items-center gap-2 rounded-lg border border-sucesso/30 bg-sucesso/5 px-4 py-3 text-sm text-sucesso">
              <CheckCircle2 className="h-4 w-4" /> Resolvida automaticamente: {data.resolucao}
            </div>
          )}
          <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
            <div className="space-y-6">
              <Cartao>
                <CabecalhoCartao titulo="Evidências" descricao="Fotos dos momentos detectados e o vídeo da visita" />
                <Evidencias detalhe={data} />
              </Cartao>
              <div className="grid gap-6 lg:grid-cols-2">
                <Cartao>
                  <CabecalhoCartao
                    titulo="Por que foi marcada"
                    descricao={data.tipo === "sem_compra" ? "Recorte ligado para esta loja: não conta score" : "Sinais somados no score (alerta a partir de 70)"}
                  />
                  <div className="px-5 pb-2">
                    <ListaMotivos motivos={data.motivos} />
                  </div>
                </Cartao>
                <Cartao>
                  <CabecalhoCartao titulo="Linha do tempo" descricao={`${formatarDuracao(data.fim - data.inicio)} na loja`} />
                  <ol className="space-y-3 p-5">
                    {data.linha_do_tempo.map((evento, indice) => (
                      <li key={indice} className="flex gap-3 text-sm">
                        <span className="w-16 shrink-0 font-mono text-xs text-fraco">{formatarHora(evento.t)}</span>
                        <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", COR_LINHA[evento.tipo])} />
                        <span>
                          {evento.texto} <span className="text-xs text-fraco">({evento.camera})</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                </Cartao>
              </div>
            </div>
            <div className="space-y-6">
              <ParecerDaIA detalhe={data} />
              <Revisao detalhe={data} />
              <Cartao>
                <CabecalhoCartao titulo="Vendas da loja por perto" descricao="TouchPay, 5 min antes e depois" />
                {!data.vendas_proximas.length && <EstadoVazio titulo="Nenhuma venda no período" />}
                <ul className="divide-y">
                  {data.vendas_proximas.map((venda) => (
                    <li key={venda.id} className={cn("px-5 py-3 text-sm", venda.id === data.pagamento?.id && "bg-sucesso/5")}>
                      <div className="flex justify-between">
                        <span className="font-medium">{formatarMoeda(venda.valor)}</span>
                        <span className="text-xs text-fraco">{formatarHora(venda.horario)}</span>
                      </div>
                      <p className="text-xs text-suave">
                        {rotuloMetodo(venda.metodo)} · {venda.itens.map((i) => `${i.quantidade}× ${i.descricao}`).join(", ") || `${venda.qtd_itens ?? "?"} item(ns)`}
                      </p>
                      {venda.visita_id && <p className="text-[11px] text-fraco">ligada à visita {venda.visita_id}</p>}
                    </li>
                  ))}
                </ul>
              </Cartao>
            </div>
          </div>
        </>
      )}
    </>
  );
}
