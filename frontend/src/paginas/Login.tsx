import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2, LockKeyhole } from "lucide-react";
import { useSessao } from "@/hooks/useSessao";
import { Botao } from "@/componentes/ui/Botao";
import { Campo, Rotulo } from "@/componentes/ui/Controles";
import { EstadoErro } from "@/componentes/ui/Estados";
import { Marca } from "@/componentes/layout/Marca";

export function Login() {
  const { usuario, entrar } = useSessao();
  const local = useLocation();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to={(local.state as { de?: string } | null)?.de ?? "/"} replace />;

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await entrar(email, senha);
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "não foi possível entrar");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-[#0b1220] lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="absolute inset-0 bg-[radial-gradient(60rem_30rem_at_20%_10%,rgba(31,111,235,0.35),transparent_70%)]" />
        <div className="relative text-white">
          <Marca />
        </div>
        <div className="relative max-w-md text-white">
          <h2 className="text-3xl font-semibold leading-tight">Prevenção de perdas para lojas autônomas</h2>
          <p className="mt-3 text-sm text-white/70">
            Câmeras em tempo real, detecção de produto na mão, conferência automática com os pagamentos da TouchPay e registro de cada
            ocorrência com fotos e vídeo.
          </p>
        </div>
        <p className="relative text-xs text-white/40">GDEL · uso interno</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={enviar} className="w-full max-w-sm space-y-5">
          <div className="lg:hidden">
            <Marca />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Entrar</h1>
            <p className="mt-1 text-sm text-suave">Use o e-mail e a senha cadastrados pelo administrador.</p>
          </div>
          {erro && <EstadoErro mensagem={erro} />}
          <Rotulo texto="E-mail">
            <Campo type="email" autoComplete="username" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </Rotulo>
          <Rotulo texto="Senha">
            <Campo type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
          </Rotulo>
          <Botao variante="primaria" type="submit" className="w-full" disabled={enviando}>
            {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}
            Entrar
          </Botao>
        </form>
      </div>
    </div>
  );
}
