import { useEffect, useState } from "react";

export function usePaginaVisivel() {
  const [visivel, setVisivel] = useState(() => document.visibilityState === "visible");

  useEffect(() => {
    const atualizar = () => setVisivel(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", atualizar);
    return () => document.removeEventListener("visibilitychange", atualizar);
  }, []);

  return visivel;
}
