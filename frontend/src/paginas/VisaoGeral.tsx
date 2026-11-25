import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CircleDollarSign, Footprints, ShieldAlert, ShoppingBasket, Video, type LucideIcon } from "lucide-react";
import { api, consulta } from "@/lib/api";
import type { Painel } from "@/lib/tipos";
import { formatarHora, formatarMoeda, formatarNumero, haQuantoTempo, porcentagem } from "@/lib/formato";
import { useLojaSelecionada } from "@/hooks/useLojaSelecionada";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Cartao, CabecalhoCartao } from "@/componentes/ui/Cartao";
import { EstadoVazio, Esqueleto } from "@/componentes/ui/Estados";
import { Indicador, SeloDoTipo, SeloSituacao } from "@/componentes/ui/Selo";
import { MovimentoPorHora } from "@/componentes/graficos/MovimentoPorHora";
import { Miniatura, motivoPrincipal } from "@/componentes/ocorrencias";
import { cn } from "@/lib/cn";

function Indicadores({ titulo, valor, detalhe, icone: Icone, destaque }: { titulo: string; valor: string; detalhe: string; icone: LucideIcon; destaque?: boolean }) {
  return (
    <Cartao className={cn("p-5", destaque && "border-alerta/40")}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-suave">{titulo}</p>
        <Icone className={cn("h-4 w-4", destaque ? "text-alerta" : "text-fraco")} />
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight">{valor}</p>
      <p className="mt-1 text-xs text-suave">{detalhe}</p>
    </Cartao>
  );
}

export function VisaoGeral() {
  const { loja } = useLojaSelecionada();
  const { data, isLoading } = useQuery({
    queryKey: ["painel", loja],
    queryFn: () => api<Painel>(`/api/painel${consulta({ loja })}`),
    refetchInterval: 15_000,
  });

  const hoje = data?.hoje;
  const online = data?.cameras.filter((c) => c.online).length ?? 0;

  return (
    <>
      <CabecalhoPagina titulo="Visão geral" descricao="Movimento de hoje nas lojas monitoradas" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading || !hoje ? (
          Array.from({ length: 4 }, (_, i) => <Esqueleto key={i} className="h-[118px] rounded-xl" />)
        ) : (
          <>
            <Indicadores
              titulo="Ocorrências abertas"
              valor={formatarNumero(hoje.ocorrencias_abertas)}
              detalhe={`${hoje.alertas_abertos} alerta(s) · ${hoje.ocorrencias} no dia`}
              icone={ShieldAlert}
              destaque={hoje.alertas_abertos > 0}
            />
            <Indicadores
              titulo="Visitas"
              valor={formatarNumero(hoje.visitas)}
              detalhe={`${hoje.visitas_com_produto} com produto na mão`}
              icone={Footprints}
            />
            <Indicadores
              titulo="Visitas pagas"
              valor={`${porcentagem(hoje.visitas_pagas, hoje.visitas_com_produto)}%`}
              detalhe={`${hoje.visitas_pagas} de ${hoje.visitas_com_produto} com produto`}
              icone={ShoppingBasket}
            />
            <Indicadores
              titulo="Vendas TouchPay"
              valor={formatarMoeda(hoje.faturamento)}
              detalhe={`${hoje.vendas} venda(s) hoje`}
              icone={CircleDollarSign}
            />
          </>
        )}
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Cartao className="xl:col-span-2">
          <CabecalhoCartao titulo="Movimento por hora" descricao="Visitas decididas e ocorrências abertas hoje" />
          <div className="p-5">{data ? <MovimentoPorHora dados={data.por_hora} /> : <Esqueleto className="h-60" />}</div>
        </Cartao>
        <Cartao>
          <CabecalhoCartao
            titulo="Câmeras"
            descricao={`${online} de ${data?.cameras.length ?? 0} com sinal`}
            acoes={
              <Link to="/ao-vivo" className="foco inline-flex items-center gap-1 rounded text-xs font-medium text-primaria">
                Ao vivo <Video className="h-3.5 w-3.5" />
              </Link>
            }
          />
          <ul className="divide-y">
            {data?.cameras.map((camera) => (
              <li key={camera.nome} className="flex items-center justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{camera.descricao}</p>
                  <p className="truncate text-xs text-fraco">
                    {camera.online ? `${camera.fps.toFixed(1)} fps · ${camera.pessoas} pessoa(s)` : camera.erro || "sem sinal"}
                  </p>
                </div>
                <Indicador ativo={camera.online} rotulo={camera.online ? "online" : "offline"} />
              </li>
            ))}
            {data && !data.cameras.length && <EstadoVazio titulo="Detecção desligada" descricao={`Situação do motor: ${data.motor}`} />}
          </ul>
        </Cartao>
      </div>

      <Cartao className="mt-6">
        <CabecalhoCartao
          titulo="Ocorrências recentes"
          acoes={
            <Link to="/ocorrencias" className="foco inline-flex items-center gap-1 rounded text-xs font-medium text-primaria">
              Ver todas <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
        {data && !data.ocorrencias_recentes.length && <EstadoVazio titulo="Nenhuma ocorrência" descricao="Quando alguém sair com produto sem pagar, aparece aqui." />}
        <ul className="divide-y">
          {data?.ocorrencias_recentes.map((o) => (
            <li key={o.id}>
              <Link to={`/ocorrencias/${o.id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-elevada/70">
                <Miniatura caminho={o.evidencias[0]} className="h-12 w-16" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{motivoPrincipal(o.motivos)}</p>
                  <p className="truncate text-xs text-fraco">
                    {o.loja_nome} · {o.cameras.join(", ")} · {formatarHora(o.inicio)} ({haQuantoTempo(o.criada_em)})
                  </p>
                </div>
                <SeloDoTipo ocorrencia={o} />
                <span className="hidden sm:inline">
                  <SeloSituacao situacao={o.situacao} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Cartao>
    </>
  );
}
