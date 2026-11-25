import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useSessao } from "@/hooks/useSessao";
import { ProvedorEventos } from "@/hooks/useEventos";
import { ProvedorLoja } from "@/hooks/useLojaSelecionada";
import { Shell } from "@/componentes/layout/Shell";
import { Login } from "@/paginas/Login";
import { VisaoGeral } from "@/paginas/VisaoGeral";
import { AoVivo } from "@/paginas/AoVivo";
import { Ocorrencias } from "@/paginas/Ocorrencias";
import { OcorrenciaDetalhe } from "@/paginas/OcorrenciaDetalhe";
import { Visitas } from "@/paginas/Visitas";
import { Vendas } from "@/paginas/Vendas";
import { Sistema } from "@/paginas/Sistema";
import { Usuarios } from "@/paginas/Usuarios";
import { Cameras } from "@/paginas/Cameras";
import { NaoEncontrada } from "@/paginas/NaoEncontrada";

function Protegida({ children }: { children: ReactNode }) {
  const { usuario, carregando } = useSessao();
  const local = useLocation();
  if (carregando) {
    return (
      <div className="flex h-full items-center justify-center text-suave">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (!usuario) return <Navigate to="/entrar" replace state={{ de: local.pathname + local.search }} />;
  return (
    <ProvedorLoja>
      <ProvedorEventos>{children}</ProvedorEventos>
    </ProvedorLoja>
  );
}

function SomenteAdmin({ children }: { children: ReactNode }) {
  const { usuario } = useSessao();
  return usuario?.papel === "admin" ? <>{children}</> : <NaoEncontrada />;
}

export function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      <Route
        element={
          <Protegida>
            <Shell />
          </Protegida>
        }
      >
        <Route index element={<VisaoGeral />} />
        <Route path="dashboard" element={<Navigate to="/" replace />} />
        <Route path="ao-vivo" element={<AoVivo />} />
        <Route path="ocorrencias" element={<Ocorrencias />} />
        <Route path="ocorrencias/:id" element={<OcorrenciaDetalhe />} />
        <Route path="visitas" element={<Visitas />} />
        <Route path="vendas" element={<Vendas />} />
        <Route path="sistema" element={<SomenteAdmin><Sistema /></SomenteAdmin>} />
        <Route path="usuarios" element={<SomenteAdmin><Usuarios /></SomenteAdmin>} />
        <Route path="cameras" element={<SomenteAdmin><Cameras /></SomenteAdmin>} />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  );
}
