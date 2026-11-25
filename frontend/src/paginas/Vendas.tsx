import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Receipt } from "lucide-react";
import { api, consulta } from "@/lib/api";
import type { Pagamento, Pagina } from "@/lib/tipos";
import { formatarDataHora, formatarMoeda, hojeIso } from "@/lib/formato";
import { rotuloMetodo } from "@/lib/rotulos";
import { useLojaSelecionada } from "@/hooks/useLojaSelecionada";
import { useFiltrosUrl } from "@/hooks/useFiltrosUrl";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Cartao } from "@/componentes/ui/Cartao";
import { Paginacao } from "@/componentes/ui/Controles";
import { EstadoVazio, LinhasCarregando } from "@/componentes/ui/Estados";
import { Selo } from "@/componentes/ui/Selo";
import { Tabela, Td, Th, Tr } from "@/componentes/ui/Tabela";
import { Periodo } from "@/componentes/Periodo";

const POR_PAGINA = 25;

export function Vendas() {
  const { loja } = useLojaSelecionada();
  const { filtros, pagina, alterar } = useFiltrosUrl({ desde: hojeIso(), ate: "" });
  const { data, isLoading } = useQuery({
    queryKey: ["vendas", loja, filtros, pagina],
    queryFn: () => api<Pagina<Pagamento> & { valor_total: number }>(`/api/vendas${consulta({ ...filtros, loja, pagina, por_pagina: POR_PAGINA })}`),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });

  return (
    <>
      <CabecalhoPagina
        titulo="Vendas"
        descricao="Pagamentos lidos da TouchPay e a visita da câmera ligada a cada um"
        acoes={<Periodo desde={filtros.desde} ate={filtros.ate} aoMudar={(desde, ate) => alterar({ desde, ate })} />}
      />
      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <Cartao className="p-5">
          <p className="text-xs text-suave">Total no período</p>
          <p className="mt-2 text-2xl font-semibold">{formatarMoeda(data?.valor_total ?? 0)}</p>
        </Cartao>
        <Cartao className="p-5">
          <p className="text-xs text-suave">Vendas</p>
          <p className="mt-2 text-2xl font-semibold">{data?.total ?? 0}</p>
        </Cartao>
      </div>
      <Cartao>
        {isLoading && <LinhasCarregando />}
        {data && !data.itens.length && <EstadoVazio icone={<Receipt className="h-5 w-5" />} titulo="Nenhuma venda no período" />}
        {data && data.itens.length > 0 && (
          <Tabela>
            <thead>
              <tr>
                <Th>Quando</Th>
                <Th>Loja</Th>
                <Th>Itens</Th>
                <Th>Forma</Th>
                <Th className="text-right">Valor</Th>
                <Th>Visita</Th>
              </tr>
            </thead>
            <tbody>
              {data.itens.map((venda) => (
                <Tr key={venda.id}>
                  <Td className="whitespace-nowrap">{formatarDataHora(venda.horario)}</Td>
                  <Td>{venda.loja_nome ?? `PDV ${venda.pdv}`}</Td>
                  <Td className="max-w-md">
                    <p className="truncate">{venda.itens.map((i) => `${i.quantidade}× ${i.descricao}`).join(", ") || `${venda.qtd_itens ?? "?"} item(ns)`}</p>
                  </Td>
                  <Td>{rotuloMetodo(venda.metodo)}</Td>
                  <Td className="text-right font-medium">{formatarMoeda(venda.valor)}</Td>
                  <Td>{venda.visita_id ? <Selo tom="sucesso">vista na câmera</Selo> : <Selo>sem visita</Selo>}</Td>
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
