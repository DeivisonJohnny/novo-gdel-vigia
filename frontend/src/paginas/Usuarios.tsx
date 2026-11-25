import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, UserPlus } from "lucide-react";
import { api, enviar } from "@/lib/api";
import type { Papel, UsuarioCadastro } from "@/lib/tipos";
import { haQuantoTempo } from "@/lib/formato";
import { useSessao } from "@/hooks/useSessao";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Botao } from "@/componentes/ui/Botao";
import { Cartao } from "@/componentes/ui/Cartao";
import { Campo, Rotulo, Selecao } from "@/componentes/ui/Controles";
import { LinhasCarregando } from "@/componentes/ui/Estados";
import { Modal } from "@/componentes/ui/Modal";
import { Selo } from "@/componentes/ui/Selo";
import { Tabela, Td, Th, Tr } from "@/componentes/ui/Tabela";

const ROTULO_PAPEL: Record<Papel, string> = { admin: "Administrador", operador: "Operador" };

function useAtualizarUsuarios() {
  const cliente = useQueryClient();
  return () => cliente.invalidateQueries({ queryKey: ["usuarios"] });
}

function NovoUsuario({ aoFechar }: { aoFechar: () => void }) {
  const atualizar = useAtualizarUsuarios();
  const [dados, setDados] = useState({ nome: "", email: "", papel: "operador" as Papel, senha: "" });
  const criar = useMutation({
    mutationFn: () => enviar("/api/usuarios", "POST", dados),
    onSuccess: () => {
      void atualizar();
      toast.success("Usuário criado");
      aoFechar();
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  const salvar = (evento: FormEvent) => {
    evento.preventDefault();
    criar.mutate();
  };
  return (
    <form onSubmit={salvar} className="space-y-4">
      <Rotulo texto="Nome">
        <Campo required value={dados.nome} onChange={(e) => setDados({ ...dados, nome: e.target.value })} />
      </Rotulo>
      <Rotulo texto="E-mail">
        <Campo type="email" required value={dados.email} onChange={(e) => setDados({ ...dados, email: e.target.value })} />
      </Rotulo>
      <Rotulo texto="Perfil">
        <Selecao value={dados.papel} onChange={(e) => setDados({ ...dados, papel: e.target.value as Papel })}>
          <option value="operador">Operador · vê câmeras e revisa ocorrências</option>
          <option value="admin">Administrador · também gerencia usuários e sistema</option>
        </Selecao>
      </Rotulo>
      <Rotulo texto="Senha inicial (mín. 8 caracteres)">
        <Campo type="password" required minLength={8} autoComplete="new-password" value={dados.senha} onChange={(e) => setDados({ ...dados, senha: e.target.value })} />
      </Rotulo>
      <Botao variante="primaria" type="submit" className="w-full" disabled={criar.isPending}>
        Criar usuário
      </Botao>
    </form>
  );
}

function NovaSenha({ usuario, aoFechar }: { usuario: UsuarioCadastro; aoFechar: () => void }) {
  const [senha, setSenha] = useState("");
  const salvar = useMutation({
    mutationFn: () => enviar(`/api/usuarios/${usuario.id}`, "PATCH", { senha }),
    onSuccess: () => {
      toast.success("Senha redefinida; as sessões abertas foram encerradas");
      aoFechar();
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  return (
    <form
      onSubmit={(evento) => {
        evento.preventDefault();
        salvar.mutate();
      }}
      className="space-y-4"
    >
      <p className="text-sm text-suave">Nova senha para {usuario.nome}.</p>
      <Campo type="password" required minLength={8} autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} className="w-full" />
      <Botao variante="primaria" type="submit" className="w-full" disabled={salvar.isPending}>
        Redefinir senha
      </Botao>
    </form>
  );
}

export function Usuarios() {
  const { usuario: eu } = useSessao();
  const atualizar = useAtualizarUsuarios();
  const [criando, setCriando] = useState(false);
  const [redefinindo, setRedefinindo] = useState<UsuarioCadastro | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["usuarios"], queryFn: () => api<UsuarioCadastro[]>("/api/usuarios") });
  const alterar = useMutation({
    mutationFn: ({ id, ...campos }: { id: number; ativo?: boolean; papel?: Papel }) => enviar(`/api/usuarios/${id}`, "PATCH", campos),
    onSuccess: () => void atualizar(),
    onError: (erro: Error) => toast.error(erro.message),
  });

  return (
    <>
      <CabecalhoPagina
        titulo="Usuários"
        descricao="Quem pode acessar o monitoramento"
        acoes={
          <Botao variante="primaria" onClick={() => setCriando(true)}>
            <UserPlus className="h-4 w-4" /> Novo usuário
          </Botao>
        }
      />
      <Cartao>
        {isLoading && <LinhasCarregando />}
        {data && (
          <Tabela>
            <thead>
              <tr>
                <Th>Nome</Th>
                <Th>Perfil</Th>
                <Th>Situação</Th>
                <Th>Último acesso</Th>
                <Th className="text-right">Ações</Th>
              </tr>
            </thead>
            <tbody>
              {data.map((usuario) => {
                const proprio = usuario.id === eu?.id;
                return (
                  <Tr key={usuario.id}>
                    <Td>
                      <p className="font-medium">
                        {usuario.nome} {proprio && <span className="text-xs text-fraco">(você)</span>}
                      </p>
                      <p className="text-xs text-fraco">{usuario.email}</p>
                    </Td>
                    <Td>
                      <Selecao
                        value={usuario.papel}
                        disabled={proprio}
                        onChange={(e) => alterar.mutate({ id: usuario.id, papel: e.target.value as Papel })}
                        className="h-8 w-40 text-xs"
                      >
                        {Object.entries(ROTULO_PAPEL).map(([valor, rotulo]) => (
                          <option key={valor} value={valor}>
                            {rotulo}
                          </option>
                        ))}
                      </Selecao>
                    </Td>
                    <Td>{usuario.ativo ? <Selo tom="sucesso">ativo</Selo> : <Selo>desativado</Selo>}</Td>
                    <Td className="text-xs text-suave">{usuario.ultimo_acesso ? haQuantoTempo(usuario.ultimo_acesso) : "nunca"}</Td>
                    <Td className="text-right">
                      <div className="flex justify-end gap-2">
                        <Botao tamanho="sm" variante="fantasma" onClick={() => setRedefinindo(usuario)}>
                          <KeyRound className="h-3.5 w-3.5" /> Senha
                        </Botao>
                        {!proprio && (
                          <Botao tamanho="sm" onClick={() => alterar.mutate({ id: usuario.id, ativo: !usuario.ativo })}>
                            {usuario.ativo ? "Desativar" : "Reativar"}
                          </Botao>
                        )}
                      </div>
                    </Td>
                  </Tr>
                );
              })}
            </tbody>
          </Tabela>
        )}
      </Cartao>
      <Modal aberto={criando} titulo="Novo usuário" aoFechar={() => setCriando(false)}>
        <NovoUsuario aoFechar={() => setCriando(false)} />
      </Modal>
      <Modal aberto={Boolean(redefinindo)} titulo="Redefinir senha" aoFechar={() => setRedefinindo(null)}>
        {redefinindo && <NovaSenha usuario={redefinindo} aoFechar={() => setRedefinindo(null)} />}
      </Modal>
    </>
  );
}
