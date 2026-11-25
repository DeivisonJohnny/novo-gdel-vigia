import { useCallback, useEffect, useState } from "react";

export type Tema = "claro" | "escuro" | "sistema";

const CHAVE = "vigia:tema";
const consultaEscuro = () => window.matchMedia("(prefers-color-scheme: dark)");

function lerTema(): Tema {
  try {
    const salvo = localStorage.getItem(CHAVE);
    return salvo === "claro" || salvo === "escuro" ? salvo : "sistema";
  } catch {
    return "sistema";
  }
}

function aplicar(tema: Tema) {
  const escuro = tema === "escuro" || (tema === "sistema" && consultaEscuro().matches);
  document.documentElement.classList.toggle("dark", escuro);
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(lerTema);

  useEffect(() => {
    aplicar(tema);
    const mudouSistema = () => tema === "sistema" && aplicar("sistema");
    const midia = consultaEscuro();
    midia.addEventListener("change", mudouSistema);
    return () => midia.removeEventListener("change", mudouSistema);
  }, [tema]);

  const escolher = useCallback((novo: Tema) => {
    setTema(novo);
    try {
      localStorage.setItem(CHAVE, novo);
    } catch {
      return;
    }
  }, []);

  return { tema, escolher };
}

aplicar(lerTema());
