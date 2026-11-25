import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, enviar } from "@/lib/api";
import type { Usuario } from "@/lib/tipos";

interface Sessao {
  usuario: Usuario | null;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
}

const ContextoSessao = createContext<Sessao | null>(null);

export function ProvedorSessao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);
  const cliente = useQueryClient();

  useEffect(() => {
    api<Usuario>("/api/auth/eu")
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCarregando(false));
    const expirou = () => {
      setUsuario(null);
      cliente.clear();
    };
    window.addEventListener("vigia:sessao-expirada", expirou);
    return () => window.removeEventListener("vigia:sessao-expirada", expirou);
  }, [cliente]);

  const entrar = useCallback(async (email: string, senha: string) => {
    setUsuario(await enviar<Usuario>("/api/auth/login", "POST", { email, senha }));
  }, []);

  const sair = useCallback(async () => {
    await enviar("/api/auth/logout", "POST").catch(() => undefined);
    setUsuario(null);
    cliente.clear();
  }, [cliente]);

  return <ContextoSessao.Provider value={{ usuario, carregando, entrar, sair }}>{children}</ContextoSessao.Provider>;
}

export function useSessao() {
  const sessao = useContext(ContextoSessao);
  if (!sessao) throw new Error("useSessao fora do ProvedorSessao");
  return sessao;
}
