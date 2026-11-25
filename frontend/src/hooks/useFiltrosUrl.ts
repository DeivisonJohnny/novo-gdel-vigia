import { useSearchParams } from "react-router-dom";

export function useFiltrosUrl<T extends Record<string, string>>(padrao: T) {
  const [busca, setBusca] = useSearchParams();
  const filtros = Object.fromEntries(Object.entries(padrao).map(([chave, valor]) => [chave, busca.get(chave) ?? valor])) as T;
  const pagina = Number(busca.get("pagina") ?? 1);

  const alterar = (mudancas: Partial<T> & { pagina?: number }) => {
    const proximo = new URLSearchParams(busca);
    Object.entries(mudancas).forEach(([chave, valor]) => {
      const vazio = valor === undefined || valor === "" || valor === padrao[chave];
      if (vazio) proximo.delete(chave);
      else proximo.set(chave, String(valor));
    });
    if (!("pagina" in mudancas)) proximo.delete("pagina");
    setBusca(proximo, { replace: true });
  };

  return { filtros, pagina, alterar };
}
