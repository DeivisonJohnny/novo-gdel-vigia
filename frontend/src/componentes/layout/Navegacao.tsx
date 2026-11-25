import { NavLink } from "react-router-dom";
import { Activity, Cctv, LayoutDashboard, Receipt, ShieldAlert, Footprints, Users, Video, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { useSessao } from "@/hooks/useSessao";
import { useOcorrenciasAbertas } from "@/hooks/useConsultas";

interface Item {
  para: string;
  rotulo: string;
  icone: LucideIcon;
  somenteAdmin?: boolean;
}

const GRUPOS: { titulo: string; itens: Item[] }[] = [
  {
    titulo: "Monitoramento",
    itens: [
      { para: "/", rotulo: "Visão geral", icone: LayoutDashboard },
      { para: "/ao-vivo", rotulo: "Ao vivo", icone: Video },
      { para: "/ocorrencias", rotulo: "Ocorrências", icone: ShieldAlert },
    ],
  },
  {
    titulo: "Registros",
    itens: [
      { para: "/visitas", rotulo: "Visitas", icone: Footprints },
      { para: "/vendas", rotulo: "Vendas", icone: Receipt },
    ],
  },
  {
    titulo: "Administração",
    itens: [
      { para: "/sistema", rotulo: "Sistema", icone: Activity, somenteAdmin: true },
      { para: "/cameras", rotulo: "Câmeras", icone: Cctv, somenteAdmin: true },
      { para: "/usuarios", rotulo: "Usuários", icone: Users, somenteAdmin: true },
    ],
  },
];

export function Navegacao({ aoNavegar }: { aoNavegar?: () => void }) {
  const { usuario } = useSessao();
  const { data: abertas = 0 } = useOcorrenciasAbertas();
  const admin = usuario?.papel === "admin";

  return (
    <nav className="flex flex-col gap-6 px-3 py-4">
      {GRUPOS.map((grupo) => {
        const itens = grupo.itens.filter((item) => admin || !item.somenteAdmin);
        if (!itens.length) return null;
        return (
          <div key={grupo.titulo}>
            <p className="px-3 pb-2 text-[11px] font-medium uppercase tracking-wider text-fraco">{grupo.titulo}</p>
            <ul className="space-y-0.5">
              {itens.map(({ para, rotulo, icone: Icone }) => (
                <li key={para}>
                  <NavLink
                    to={para}
                    end={para === "/"}
                    onClick={aoNavegar}
                    className={({ isActive }) =>
                      cn(
                        "foco flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                        isActive ? "bg-primaria/10 font-medium text-primaria" : "text-suave hover:bg-elevada hover:text-texto",
                      )
                    }
                  >
                    <Icone className="h-4 w-4" />
                    <span className="flex-1">{rotulo}</span>
                    {para === "/ocorrencias" && abertas > 0 && (
                      <span className="rounded-full bg-alerta px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">
                        {abertas > 99 ? "99+" : abertas}
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
