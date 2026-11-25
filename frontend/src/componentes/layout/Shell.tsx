import { useState } from "react";
import { Outlet } from "react-router-dom";
import { LogOut, Menu, Monitor, Moon, Sun, X } from "lucide-react";
import { useSessao } from "@/hooks/useSessao";
import { useTema, type Tema } from "@/hooks/useTema";
import { useEventos } from "@/hooks/useEventos";
import { useLojaSelecionada } from "@/hooks/useLojaSelecionada";
import { useLojas } from "@/hooks/useConsultas";
import { cn } from "@/lib/cn";
import { Botao } from "../ui/Botao";
import { Selecao } from "../ui/Controles";
import { Indicador } from "../ui/Selo";
import { Marca } from "./Marca";
import { Navegacao } from "./Navegacao";
import { Notificacoes } from "./Notificacoes";

const PROXIMO_TEMA: Record<Tema, { proximo: Tema; icone: typeof Sun; rotulo: string }> = {
  sistema: { proximo: "claro", icone: Monitor, rotulo: "Tema do sistema" },
  claro: { proximo: "escuro", icone: Sun, rotulo: "Tema claro" },
  escuro: { proximo: "sistema", icone: Moon, rotulo: "Tema escuro" },
};

function SeletorLoja() {
  const { loja, setLoja } = useLojaSelecionada();
  const { data: lojas = [] } = useLojas();
  return (
    <Selecao value={loja} onChange={(evento) => setLoja(evento.target.value)} aria-label="Filtrar por loja" className="min-w-0 max-w-52 flex-1 sm:w-52 sm:flex-none">
      <option value="">Todas as lojas</option>
      {lojas.map((l) => (
        <option key={l.id} value={l.id}>
          {l.nome}
        </option>
      ))}
    </Selecao>
  );
}

function MenuUsuario() {
  const { usuario, sair } = useSessao();
  if (!usuario) return null;
  const iniciais = usuario.nome.split(" ").map((parte) => parte[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className="flex items-center gap-2 border-l pl-2 sm:pl-3">
      <div className="hidden text-right leading-tight md:block">
        <p className="text-xs font-medium">{usuario.nome}</p>
        <p className="text-[11px] text-fraco">{usuario.papel === "admin" ? "Administrador" : "Operador"}</p>
      </div>
      <div className="hidden h-8 w-8 items-center justify-center rounded-full bg-primaria/15 sm:flex text-xs font-semibold text-primaria">{iniciais}</div>
      <Botao variante="fantasma" tamanho="sm" onClick={() => void sair()} aria-label="Sair" title="Sair">
        <LogOut className="h-4 w-4" />
      </Botao>
    </div>
  );
}

export function Shell() {
  const [menuAberto, setMenuAberto] = useState(false);
  const { tema, escolher } = useTema();
  const { conectado } = useEventos();
  const { icone: IconeTema, rotulo, proximo } = PROXIMO_TEMA[tema];

  return (
    <div className="flex h-full">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-superficie transition-transform lg:static lg:translate-x-0",
          menuAberto ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b px-5">
          <Marca />
          <Botao variante="fantasma" tamanho="sm" className="lg:hidden" onClick={() => setMenuAberto(false)} aria-label="Fechar menu">
            <X className="h-4 w-4" />
          </Botao>
        </div>
        <div className="rolagem flex-1 overflow-y-auto">
          <Navegacao aoNavegar={() => setMenuAberto(false)} />
        </div>
        <div className="border-t px-5 py-3">
          <Indicador ativo={conectado} pulsar rotulo={conectado ? "Tempo real conectado" : "Reconectando…"} />
        </div>
      </aside>
      {menuAberto && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setMenuAberto(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b bg-superficie/85 px-4 backdrop-blur sm:px-6">
          <Botao variante="fantasma" tamanho="sm" className="lg:hidden" onClick={() => setMenuAberto(true)} aria-label="Abrir menu">
            <Menu className="h-4 w-4" />
          </Botao>
          <SeletorLoja />
          <div className="ml-auto flex shrink-0 items-center sm:gap-1">
            <Notificacoes />
            <Botao variante="fantasma" tamanho="sm" onClick={() => escolher(proximo)} aria-label={rotulo} title={rotulo}>
              <IconeTema className="h-4 w-4" />
            </Botao>
            <MenuUsuario />
          </div>
        </header>
        <main className="rolagem flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export function CabecalhoPagina({ titulo, descricao, acoes }: { titulo: string; descricao?: string; acoes?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{titulo}</h1>
        {descricao && <p className="mt-1 text-sm text-suave">{descricao}</p>}
      </div>
      {acoes && <div className="flex flex-wrap items-center gap-2">{acoes}</div>}
    </div>
  );
}
