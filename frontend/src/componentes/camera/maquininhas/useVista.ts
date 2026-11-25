import { useCallback, useEffect, useRef, useState } from "react";
import type { Caixa } from "@/lib/tipos";
import { limitar, type Ponto } from "./geometria";

export const ESCALA_MAXIMA = 8;
const PASSO_ZOOM = 1.25;
const PASSO_ZOOM_RODA = 1.15;
const FRACAO_DA_TELA_AO_FOCAR = 0.45;

export interface Vista {
  escala: number;
  x: number;
  y: number;
}

const VISTA_INTEIRA: Vista = { escala: 1, x: 0, y: 0 };

function enquadrar(vista: Vista, largura: number, altura: number): Vista {
  const escala = limitar(vista.escala, 1, ESCALA_MAXIMA);
  return {
    escala,
    x: limitar(vista.x, largura - largura * escala, 0),
    y: limitar(vista.y, altura - altura * escala, 0),
  };
}

export function useVista() {
  const janela = useRef<HTMLDivElement>(null);
  const [vista, setVista] = useState<Vista>(VISTA_INTEIRA);

  const tamanho = useCallback(() => ({ largura: janela.current?.clientWidth ?? 0, altura: janela.current?.clientHeight ?? 0 }), []);

  const zoomEm = useCallback(
    (fator: number, foco?: Ponto) => {
      setVista((atual) => {
        const { largura, altura } = tamanho();
        const centro = foco ?? { x: largura / 2, y: altura / 2 };
        const escala = limitar(atual.escala * fator, 1, ESCALA_MAXIMA);
        const proporcao = escala / atual.escala;
        return enquadrar(
          { escala, x: centro.x - (centro.x - atual.x) * proporcao, y: centro.y - (centro.y - atual.y) * proporcao },
          largura,
          altura,
        );
      });
    },
    [tamanho],
  );

  const deslocarPara = useCallback(
    (x: number, y: number) => {
      const { largura, altura } = tamanho();
      setVista((atual) => enquadrar({ ...atual, x, y }, largura, altura));
    },
    [tamanho],
  );

  const focar = useCallback(
    ([x1, y1, x2, y2]: Caixa) => {
      const { largura, altura } = tamanho();
      const escala = limitar(FRACAO_DA_TELA_AO_FOCAR / Math.max(x2 - x1, y2 - y1, 0.01), 1, ESCALA_MAXIMA);
      const centroX = ((x1 + x2) / 2) * largura * escala;
      const centroY = ((y1 + y2) / 2) * altura * escala;
      setVista(enquadrar({ escala, x: largura / 2 - centroX, y: altura / 2 - centroY }, largura, altura));
    },
    [tamanho],
  );

  const aumentar = useCallback(() => zoomEm(PASSO_ZOOM), [zoomEm]);
  const diminuir = useCallback(() => zoomEm(1 / PASSO_ZOOM), [zoomEm]);
  const verInteira = useCallback(() => setVista(VISTA_INTEIRA), []);

  useEffect(() => {
    const elemento = janela.current;
    if (!elemento) return;
    const rolar = (evento: WheelEvent) => {
      evento.preventDefault();
      const limites = elemento.getBoundingClientRect();
      zoomEm(evento.deltaY < 0 ? PASSO_ZOOM_RODA : 1 / PASSO_ZOOM_RODA, { x: evento.clientX - limites.left, y: evento.clientY - limites.top });
    };
    elemento.addEventListener("wheel", rolar, { passive: false });
    return () => elemento.removeEventListener("wheel", rolar);
  }, [zoomEm]);

  return { janela, vista, zoomEm, deslocarPara, focar, aumentar, diminuir, verInteira };
}

export type ControleDaVista = ReturnType<typeof useVista>;
