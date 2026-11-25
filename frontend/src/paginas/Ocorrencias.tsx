import { useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { api, consulta } from "@/lib/api";
import type { Ocorrencia, Pagina } from "@/lib/tipos";
import { formatarDataHora, formatarDuracao } from "@/lib/formato";
import { useLojaSelecionada } from "@/hooks/useLojaSelecionada";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Cartao } from "@/componentes/ui/Cartao";
import { Paginacao, Segmentado, Selecao } from "@/componentes/ui/Controles";
import { EstadoErro, EstadoVazio, LinhasCarregando } from "@/componentes/ui/Estados";
import { SeloDoTipo, SeloIA, SeloSituacao, SeloVeredito } from "@/componentes/ui/Selo";
import { Tabela, Td, Th, Tr } from "@/componentes/ui/Tabela";
import { BarraScore, Miniatura, motivoPrincipal } from "@/componentes/ocorrencias";
import { Periodo } from "@/componentes/Periodo";

const POR_PAGINA = 20;
type Aba = "aberta" | "triagem" | "descartada" | "resolvida" | "revisada" | "todas";

const DESCRICAO_VAZIO: Record<string, string> = {
  aberta: "Ocorrências abertas já passaram pela IA e aguardam revisão de um operador.",
  triagem: "A IA analisa as fotos e o vídeo de cada ocorrência antes de ela chegar à fila.",
  descartada: "Aqui ficam as ocorrências que a IA viu como falso positivo com confiança alta.",
};

export function Ocorrencias() {
  const navegar = useNavigate();
  const { loja } = useLojaSelecionada();
  const { filtros, pagina, alterar } = useFiltrosUrl({ situacao: "aberta", tipo: "", nivel: "", desde: "", ate: "" });
  const { data, isLoading, error } = useQuery({
    queryKey: ["ocorrencias", "lista", loja, filtros, pagina],
    queryFn: () =>
      api<Pagina<Ocorrencia>>(
        `/api/ocorrencias${consulta({ ...filtros, situacao: filtros.situacao === "todas" ? "" : filtros.situacao, loja, pagina, por_pagina: POR_PAGINA })}`,
      ),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

  return (
    <>
      <CabecalhoPagina titulo="Ocorrências" descricao="Visitas em que alguém pegou produto sem pagamento confirmado e, nas lojas com o recorte ligado, quem entrou e saiu sem comprar" />
      <Cartao>
        <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
          <Segmentado<Aba>
            valor={filtros.situacao as Aba}
            aoMudar={(situacao) => alterar({ situacao })}
            opcoes={[
              { valor: "aberta", rotulo: "Abertas" },
              { valor: "triagem", rotulo: "Na triagem da IA" },
              { valor: "descartada", rotulo: "Descartadas pela IA" },
              { valor: "revisada", rotulo: "Revisadas" },
              { valor: "resolvida", rotulo: "Resolvidas" },
              { valor: "todas", rotulo: "Todas" },
            ]}
          />
          <Selecao value={filtros.tipo} onChange={(e) => alterar({ tipo: e.target.value })} aria-label="Tipo" className="w-48">
            <option value="">Todos os tipos</option>
            <option value="suspeita">Suspeita de furto</option>
            <option value="sem_compra">Entrou sem comprar</option>
          </Selecao>
          <Selecao value={filtros.nivel} onChange={(e) => alterar({ nivel: e.target.value })} aria-label="Nível" className="w-36">
            <option value="">Todos os níveis</option>
            <option value="alerta">Alerta</option>
            <option value="atencao">Atenção</option>
          </Selecao>
          <div className="ml-auto">
            <Periodo desde={filtros.desde} ate={filtros.ate} aoMudar={(desde, ate) => alterar({ desde, ate })} />
          </div>
        </div>
        {error && <div className="p-5"><EstadoErro mensagem={(error as Error).message} /></div>}
        {isLoading && <LinhasCarregando />}
        {data && !data.itens.length && (
          <EstadoVazio
            icone={<ShieldCheck className="h-5 w-5" />}
            titulo={filtros.situacao === "aberta" ? "Nenhuma ocorrência aberta" : "Nada encontrado"}
            descricao={DESCRICAO_VAZIO[filtros.situacao]}
          />
        )}
        {data && data.itens.length > 0 && (
          <Tabela>
            <thead>
              <tr>
                <Th>Evidência</Th>
                <Th>Quando</Th>
                <Th>Loja / câmera</Th>
                <Th>Motivo principal</Th>
                <Th>Tipo / nível</Th>
                <Th>Score</Th>
                <Th>Situação / IA</Th>
              </tr>
            </thead>
            <tbody>
              {data.itens.map((o) => (
                <Tr key={o.id} clicavel onClick={() => navegar(`/ocorrencias/${o.id}`)}>
                  <Td className="w-24">
                    <Miniatura caminho={o.evidencias[0]} className="h-12 w-16" />
                  </Td>
                  <Td className="whitespace-nowrap">
                    <p className="font-medium">{formatarDataHora(o.inicio)}</p>
                    <p className="text-xs text-fraco">{formatarDuracao(o.fim - o.inicio)} na loja</p>
                  </Td>
                  <Td>
                    <p>{o.loja_nome}</p>
                    <p className="text-xs text-fraco">{o.cameras.join(", ")}</p>
                  </Td>
                  <Td className="max-w-sm">
                    <p className="truncate">{motivoPrincipal(o.motivos)}</p>
                    {o.ia?.resumo && <p className="truncate text-xs text-suave">IA: {o.ia.resumo}</p>}
                    {o.resolucao && <p className="truncate text-xs text-sucesso">{o.resolucao}</p>}
                  </Td>
                  <Td>
                    <SeloDoTipo ocorrencia={o} />
                  </Td>
                  <Td>
                    {o.tipo === "sem_compra" ? <span className="text-xs text-fraco">—</span> : <BarraScore score={o.score} />}
                  </Td>
                  <Td>
                    <div className="flex flex-col items-start gap-1">
                      {o.veredito ? <SeloVeredito veredito={o.veredito} /> : <SeloSituacao situacao={o.situacao} />}
                      {o.situacao !== "triagem" && <SeloIA ia={o.ia} situacao={o.situacao} />}
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Tabela>
        )}
        {data && data.total > 0 && <Paginacao pagina={pagina} porPagina={POR_PAGINA} total={data.total} aoMudar={(p) => alterar({ pagina: p })} />}
      </Cartao>
    </>
  );
}
