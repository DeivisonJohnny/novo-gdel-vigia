import { useEffect, useState, type RefObject } from "react";

export type ModoVideo = "conectando" | "webrtc" | "mjpeg";

const TEMPO_COLETA_ICE_MS = 1500;
const ESPERA_NOVA_TENTATIVA_MS = 30_000;
const ESTADOS_DE_FALHA = new Set<RTCPeerConnectionState>(["failed", "disconnected", "closed"]);

function aguardarCandidatos(conexao: RTCPeerConnection) {
  return new Promise<void>((resolver) => {
    if (conexao.iceGatheringState === "complete") return resolver();
    const prazo = setTimeout(resolver, TEMPO_COLETA_ICE_MS);
    conexao.addEventListener("icegatheringstatechange", () => {
      if (conexao.iceGatheringState === "complete") {
        clearTimeout(prazo);
        resolver();
      }
    });
  });
}

async function negociar(camera: string, conexao: RTCPeerConnection) {
  conexao.addTransceiver("video", { direction: "recvonly" });
  await conexao.setLocalDescription(await conexao.createOffer());
  await aguardarCandidatos(conexao);
  const resposta = await fetch(`/api/cameras/${encodeURIComponent(camera)}/whep`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/sdp" },
    body: conexao.localDescription?.sdp,
  });
  if (resposta.status !== 201) throw new Error(`WHEP ${resposta.status}`);
  await conexao.setRemoteDescription({ type: "answer", sdp: await resposta.text() });
  return resposta.headers.get("Location");
}

export function useWebRTC(camera: string, habilitado: boolean, video: RefObject<HTMLVideoElement>) {
  const [modo, setModo] = useState<ModoVideo>(habilitado ? "conectando" : "mjpeg");

  useEffect(() => {
    if (!habilitado) {
      setModo("mjpeg");
      return;
    }
    let ativo = true;
    let conexao: RTCPeerConnection | null = null;
    let sessao: string | null = null;
    let novaTentativa: ReturnType<typeof setTimeout> | undefined;

    const encerrar = () => {
      conexao?.close();
      conexao = null;
      if (sessao) void fetch(sessao, { method: "DELETE", credentials: "same-origin" }).catch(() => undefined);
      sessao = null;
    };

    const cairParaMjpeg = () => {
      encerrar();
      if (!ativo) return;
      setModo("mjpeg");
      novaTentativa = setTimeout(conectar, ESPERA_NOVA_TENTATIVA_MS);
    };

    async function conectar() {
      if (!ativo) return;
      conexao = new RTCPeerConnection();
      conexao.ontrack = (evento) => {
        if (video.current) video.current.srcObject = evento.streams[0] ?? new MediaStream([evento.track]);
      };
      conexao.onconnectionstatechange = () => {
        const estado = conexao?.connectionState;
        if (estado === "connected") setModo("webrtc");
        if (estado && ESTADOS_DE_FALHA.has(estado)) cairParaMjpeg();
      };
      try {
        sessao = await negociar(camera, conexao);
      } catch {
        cairParaMjpeg();
      }
    }

    void conectar();
    return () => {
      ativo = false;
      clearTimeout(novaTentativa);
      encerrar();
    };
  }, [camera, habilitado, video]);

  return modo;
}
