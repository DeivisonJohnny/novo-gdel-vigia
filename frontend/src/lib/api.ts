export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

async function mensagemDeErro(resposta: Response) {
  try {
    const corpo = await resposta.json();
    return typeof corpo.detail === "string" ? corpo.detail : "não foi possível concluir a operação";
  } catch {
    return resposta.statusText || "erro de comunicação com o servidor";
  }
}

const TEMPO_LIMITE_MS = 20_000;

function comTempoLimite(sinal?: AbortSignal | null) {
  const limite = AbortSignal.timeout(TEMPO_LIMITE_MS);
  return sinal && "any" in AbortSignal ? AbortSignal.any([sinal, limite]) : sinal ?? limite;
}

export async function api<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, {
      credentials: "same-origin",
      ...opcoes,
      signal: comTempoLimite(opcoes.signal),
      headers: { ...(opcoes.body ? { "Content-Type": "application/json" } : {}), ...opcoes.headers },
    });
  } catch (erro) {
    if (erro instanceof DOMException && erro.name === "TimeoutError") throw new ErroApi(0, "o servidor demorou para responder; tente de novo");
    throw erro;
  }
  if (resposta.status === 401 && !caminho.startsWith("/api/auth/")) {
    window.dispatchEvent(new Event("vigia:sessao-expirada"));
  }
  if (!resposta.ok) throw new ErroApi(resposta.status, await mensagemDeErro(resposta));
  return resposta.status === 204 ? (undefined as T) : resposta.json();
}

export const enviar = <T>(caminho: string, metodo: string, corpo?: unknown) =>
  api<T>(caminho, { method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });

export function consulta(parametros: Record<string, string | number | null | undefined>) {
  const busca = new URLSearchParams();
  Object.entries(parametros).forEach(([chave, valor]) => {
    if (valor !== null && valor !== undefined && valor !== "") busca.set(chave, String(valor));
  });
  const texto = busca.toString();
  return texto ? `?${texto}` : "";
}

export const urlArquivo = (caminho: string) => `/api/arquivos/${caminho.split("/").map(encodeURIComponent).join("/")}`;
