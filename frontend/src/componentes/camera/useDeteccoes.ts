import { useEffect, useRef, type MutableRefObject } from "react";
import type { Deteccao } from "@/lib/tipos";

export interface DeteccaoRecebida {
  deteccao: Deteccao;
  recebidaEm: number;
}

export type MapaDeteccoes = MutableRefObject<Map<string, DeteccaoRecebida>>;

export function useDeteccoes(cameras: string[], habilitado: boolean): MapaDeteccoes {
  const ultimas = useRef(new Map<string, DeteccaoRecebida>());
  const chave = cameras.join(",");

  useEffect(() => {
    ultimas.current.clear();
    if (!habilitado || !chave) return;
    const fonte = new EventSource(`/api/cameras/deteccoes?cameras=${encodeURIComponent(chave)}`);
    fonte.onmessage = (mensagem) => {
      const { camera, deteccao } = JSON.parse(mensagem.data);
      ultimas.current.set(camera, { deteccao, recebidaEm: performance.now() });
    };
    return () => fonte.close();
  }, [chave, habilitado]);

  return ultimas;
}
