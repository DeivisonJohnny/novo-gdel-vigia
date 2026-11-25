import { createContext, useContext, useState, type ReactNode } from "react";

const CHAVE = "vigia:loja";

interface LojaSelecionada {
  loja: string;
  setLoja: (loja: string) => void;
}

const ContextoLoja = createContext<LojaSelecionada | null>(null);

function lerLoja() {
  try {
    return localStorage.getItem(CHAVE) ?? "";
  } catch {
    return "";
  }
}

export function ProvedorLoja({ children }: { children: ReactNode }) {
  const [loja, setLojaEstado] = useState(lerLoja);
  const setLoja = (nova: string) => {
    setLojaEstado(nova);
    try {
      localStorage.setItem(CHAVE, nova);
    } catch {
      return;
    }
  };
  return <ContextoLoja.Provider value={{ loja, setLoja }}>{children}</ContextoLoja.Provider>;
}

export function useLojaSelecionada() {
  const contexto = useContext(ContextoLoja);
  if (!contexto) throw new Error("useLojaSelecionada fora do ProvedorLoja");
  return contexto;
}
