import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Loja, Ocorrencia, Pagina } from "@/lib/tipos";

export function useLojas() {
  return useQuery({ queryKey: ["lojas"], queryFn: () => api<Loja[]>("/api/lojas"), staleTime: 5 * 60_000 });
}

export function useOcorrenciasAbertas() {
  return useQuery({
    queryKey: ["ocorrencias", "abertas"],
    queryFn: () => api<Pagina<Ocorrencia> & { abertas: number }>("/api/ocorrencias?situacao=aberta&por_pagina=1"),
    refetchInterval: 60_000,
    select: (dados) => dados.abertas,
  });
}
