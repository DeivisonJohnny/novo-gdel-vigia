import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, Footprints } from "lucide-react";
import { api, consulta } from "@/lib/api";
import type { Pagina, ResultadoVisita, Visita } from "@/lib/tipos";
import { formatarDataHora, formatarDuracao, formatarMoeda } from "@/lib/formato";
import { rotuloMetodo } from "@/lib/rotulos";
import { cn } from "@/lib/cn";
import { useLojaSelecionada } from "@/hooks/useLojaSelecionada";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Cartao } from "@/componentes/ui/Cartao";
import { Paginacao, Segmentado } from "@/componentes/ui/Controles";
import { EstadoVazio, LinhasCarregando } from "@/componentes/ui/Estados";
import { Selo, SeloNivel } from "@/componentes/ui/Selo";
import { Tabela, Td, Th, Tr } from "@/componentes/ui/Tabela";
import { ListaMotivos } from "@/componentes/ocorrencias";
import { Periodo } from "@/componentes/Periodo";

const POR_PAGINA = 25;
type Filtro = ResultadoVisita | "todas";

function Pagamento({ visita }: { visita: Visita }) {
  if (visita.pagamento_id) {
    return (
      <div>
        <p className="font-medium text-sucesso">{formatarMoeda(visita.valor)}</p>
        <p className="text-xs text-fraco">
          {rotuloMetodo(visita.metodo)} · {visita.qtd_itens ?? "?"} item(ns)
        </p>
      </div>
    );
  }
  return visita.pegadas ? <Selo tom="atencao">sem pagamento</Selo> : <span className="text-xs text-fraco">—</span>;
}

export function Visitas() {
  const { loja } = useLojaSelecionada();
  const [aberta, setAberta] = useState<string | null>(null);
  const { filtros, pagina, alterar } = useFiltrosUrl({ resultado: "todas", desde: "", ate: "" });
  const { data, isLoading } = useQuery({
    queryKey: ["visitas", loja, filtros, pagina],
    queryFn: () =>
      api<Pagina<Visita>>(
        `/api/visitas${consulta({ ...filtros, resultado: filtros.resultado === "todas" ? "" : filtros.resultado, loja, pagina, por_pagina: POR_PAGINA })}`,
      ),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

  return (
    <>
      <CabecalhoPagina titulo="Visitas" descricao="Cada pessoa que entrou, o que a câmera viu e se o pagamento foi confirmado" />
      <Cartao>
        <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
          <Segmentado<Filtro>
            valor={filtros.resultado as Filtro}
            aoMudar={(resultado) => alterar({ resultado })}
            opcoes={[
              { valor: "todas", rotulo: "Todas" },
              { valor: "pagas", rotulo: "Pagas" },
              { valor: "sem_pagamento", rotulo: "Pegou sem pagar" },
              { valor: "sem_produto", rotulo: "Sem produto" },
              { valor: "suspeitas", rotulo: "Suspeitas" },
            ]}
          />
          <div className="ml-auto">
            <Periodo desde={filtros.desde} ate={filtros.ate} aoMudar={(desde, ate) => alterar({ desde, ate })} />
          </div>
        </div>
        {isLoading && <LinhasCarregando />}
        {data && !data.itens.length && <EstadoVazio icone={<Footprints className="h-5 w-5" />} titulo="Nenhuma visita encontrada" />}
        {data && data.itens.length > 0 && (
          <Tabela>
            <thead>
              <tr>
                <Th className="w-8" />
                <Th>Quando</Th>
                <Th>Loja / câmeras</Th>
                <Th>Produto na mão</Th>
                <Th>Totem</Th>
                <Th>Pagamento</Th>
                <Th>Resultado</Th>
              </tr>
            </thead>
            <tbody>
              {data.itens.map((visita) => (
                <Fragment key={visita.id}>
                  <Tr clicavel onClick={() => setAberta(aberta === visita.id ? null : visita.id)}>
                    <Td>
                      <ChevronDown className={cn("h-4 w-4 text-fraco transition-transform", aberta === visita.id && "rotate-180")} />
                    </Td>
                    <Td className="whitespace-nowrap">
                      <p className="font-medium">{formatarDataHora(visita.inicio)}</p>
                      <p className="text-xs text-fraco">{formatarDuracao(visita.fim - visita.inicio)}</p>
                    </Td>
                    <Td>
                      <p>{visita.loja_nome}</p>
                      <p className="text-xs text-fraco">{visita.cameras.join(", ")}</p>
                    </Td>
                    <Td>{visita.pegadas ? `${visita.pegadas}×` : <span className="text-fraco">não</span>}</Td>
                    <Td>{visita.foi_totem ? "passou" : <span className="text-fraco">não</span>}</Td>
                    <Td>
                      <Pagamento visita={visita} />
                    </Td>
                    <Td>
                      {visita.ocorrencia_id ? (
                        <Link to={`/ocorrencias/${visita.ocorrencia_id}`} onClick={(e) => e.stopPropagation()} className="foco rounded">
                          <SeloNivel nivel={visita.nivel} />
                        </Link>
                      ) : (
                        <SeloNivel nivel={visita.nivel} />
                      )}
                    </Td>
                  </Tr>
                  {aberta === visita.id && (
                    <tr>
                      <td colSpan={7} className="border-b bg-elevada/50 px-14 py-3">
                        <ListaMotivos motivos={visita.motivos} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </Tabela>
        )}
        {data && data.total > 0 && <Paginacao pagina={pagina} porPagina={POR_PAGINA} total={data.total} aoMudar={(p) => alterar({ pagina: p })} />}
      </Cartao>
    </>
  );
}
