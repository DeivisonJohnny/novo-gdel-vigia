import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OrigemTotem, StatusSistema } from "@/lib/tipos";
import { formatarDataHora, haQuantoTempo } from "@/lib/formato";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Cartao, CabecalhoCartao } from "@/componentes/ui/Cartao";
import { EstadoErro, Esqueleto } from "@/componentes/ui/Estados";
import { Indicador, Selo } from "@/componentes/ui/Selo";
import { Tabela, Td, Th, Tr } from "@/componentes/ui/Tabela";

const ROTULO_TOTEM: Record<OrigemTotem, string> = {
  manual: "marcado pelo admin",
  sem_maquininha: "sem maquininha (admin)",
  configurado: "configurado",
  aprendido: "aprendido pela IA",
  procurando: "procurando a maquininha",
};

function Linha({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 text-sm">
      <span className="text-suave">{rotulo}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}

const quando = (t?: number | null) => (t ? `${formatarDataHora(t)} (${haQuantoTempo(t)})` : "—");

export function Sistema() {
  const { data, isLoading, error } = useQuery({ queryKey: ["sistema"], queryFn: () => api<StatusSistema>("/api/sistema"), refetchInterval: 5_000 });
  const motor = data?.motor;

  return (
    <>
      <CabecalhoPagina titulo="Sistema" descricao={data ? `Versão ${data.versao} · ambiente ${data.ambiente}` : undefined} />
      {error && <EstadoErro mensagem={(error as Error).message} />}
      {isLoading && <Esqueleto className="h-64 rounded-xl" />}
      {motor && (
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-4">
          <Cartao>
            <CabecalhoCartao titulo="Detecção" />
            <div className="divide-y px-5 pb-3">
              <Linha rotulo="Situação">
                <Indicador ativo={motor.situacao === "rodando"} rotulo={motor.situacao} pulsar />
              </Linha>
              {motor.erro && <p className="py-2 text-xs text-alerta">{motor.erro}</p>}
              <Linha rotulo="Modelo">{motor.modelo?.arquivo ?? "—"}</Linha>
              <Linha rotulo="Classes">{motor.modelo?.classes.join(", ") ?? "—"}</Linha>
              <Linha rotulo="Tempo por inferência">{motor.modelo ? `${motor.modelo.inferencia_ms} ms` : "—"}</Linha>
              <Linha rotulo="Desde">{quando(motor.iniciado_em)}</Linha>
              <Linha rotulo="Visitas aguardando decisão">{motor.visitas_em_andamento?.length ?? 0}</Linha>
            </div>
          </Cartao>
          <Cartao>
            <CabecalhoCartao titulo="TouchPay" />
            <div className="divide-y px-5 pb-3">
              <Linha rotulo="Conexão">
                <Indicador ativo={Boolean(motor.touchpay?.configurado && !motor.touchpay.erro_vendas)} rotulo={motor.touchpay?.erro_vendas ? "com erro" : "ok"} />
              </Linha>
              {motor.touchpay?.erro_vendas && <p className="py-2 text-xs text-alerta">{motor.touchpay.erro_vendas}</p>}
              <Linha rotulo="PDVs">{motor.touchpay?.pdvs.join(", ") || "—"}</Linha>
              <Linha rotulo="Última consulta">{quando(motor.touchpay?.ultima_consulta)}</Linha>
              <Linha rotulo="Última venda recebida">{quando(motor.touchpay?.ultimo_recebido)}</Linha>
              <Linha rotulo="Vendas lidas nesta execução">{motor.touchpay?.recebidos ?? 0}</Linha>
            </div>
          </Cartao>
          <Cartao>
            <CabecalhoCartao titulo="Triagem por IA" />
            <div className="divide-y px-5 pb-3">
              <Linha rotulo="Situação">
                <Indicador ativo={Boolean(motor.triagem?.ativa)} rotulo={motor.triagem?.ativa ? "ligada" : "desligada"} />
              </Linha>
              {motor.triagem?.ultimo_erro && <p className="py-2 text-xs text-alerta">{motor.triagem.ultimo_erro}</p>}
              <Linha rotulo="Modelo">{motor.triagem?.modelo ?? "—"}</Linha>
              <Linha rotulo="Analisa ocorrências com score">{`acima de ${motor.triagem?.score_acima_de ?? 0}`}</Linha>
              <Linha rotulo="Na fila agora">{motor.triagem?.na_fila ?? 0}</Linha>
              <Linha rotulo="Analisadas nesta execução">{motor.triagem?.analisadas ?? 0}</Linha>
              <Linha rotulo="Enviadas ao operador">{motor.triagem?.encaminhadas ?? 0}</Linha>
              <Linha rotulo="Descartadas como falso positivo">{motor.triagem?.descartadas ?? 0}</Linha>
              <Linha rotulo="Falhas da API">{motor.triagem?.erros ?? 0}</Linha>
            </div>
          </Cartao>
          <Cartao>
            <CabecalhoCartao titulo="Armazenamento" />
            <div className="divide-y px-5 pb-3">
              <Linha rotulo="Disco livre">{motor.disco ? `${motor.disco.livre_gb} de ${motor.disco.total_gb} GB` : "—"}</Linha>
              <Linha rotulo="Clipes das ocorrências">{motor.clipes_ativos ? "ativos" : "desligados"}</Linha>
              <Linha rotulo="Coleta para treino">{motor.coleta?.ativa ? "ligada" : "desligada"}</Linha>
              <Linha rotulo="Imagens coletadas hoje">
                {Object.values(motor.coleta?.hoje ?? {}).reduce((soma, n) => soma + n, 0)}
              </Linha>
            </div>
          </Cartao>
          <Cartao className="lg:col-span-2 xl:col-span-4">
            <CabecalhoCartao titulo="Câmeras" />
            <Tabela>
              <thead>
                <tr>
                  <Th>Câmera</Th>
                  <Th>Sinal</Th>
                  <Th>FPS da análise</Th>
                  <Th>Uso da IA</Th>
                  <Th>Pessoas agora</Th>
                  <Th>Totem</Th>
                  <Th>Caminho no roteador</Th>
                </tr>
              </thead>
              <tbody>
                {data.cameras.map((camera) => (
                  <Tr key={camera.nome}>
                    <Td>
                      <p className="font-medium">{camera.descricao}</p>
                      <p className="text-xs text-fraco">{camera.nome}</p>
                    </Td>
                    <Td>
                      <Indicador ativo={camera.online} rotulo={camera.online ? "online" : camera.erro || "offline"} />
                    </Td>
                    <Td>{camera.fps.toFixed(1)}</Td>
                    <Td>{Math.round(camera.uso_ia * 100)}%</Td>
                    <Td>{camera.pessoas}</Td>
                    <Td>
                      <Selo tom={camera.cobre_totem ? "sucesso" : "neutro"}>{ROTULO_TOTEM[camera.origem_totem]}</Selo>
                    </Td>
                    <Td className="font-mono text-xs text-suave">{camera.caminho}</Td>
                  </Tr>
                ))}
              </tbody>
            </Tabela>
          </Cartao>
        </div>
      )}
    </>
  );
}
