import { useState, type FormEvent, type KeyboardEvent, type MouseEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Check, Copy, Pencil, Plus, Save, Scan, Search, Trash2, X } from "lucide-react";
import { api, enviar } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { CadastroCameras, CameraCadastro, CameraCriada, LojaCadastro, PdvTouchPay } from "@/lib/tipos";
import { haQuantoTempo } from "@/lib/formato";
import { EditorMaquininhas } from "@/componentes/camera/maquininhas/EditorMaquininhas";
import { EditorRecorteSemCompra, SituacaoRecorte } from "@/componentes/lojas/RecorteSemCompra";
import { CabecalhoPagina } from "@/componentes/layout/Shell";
import { Botao } from "@/componentes/ui/Botao";
import { CabecalhoCartao, Cartao } from "@/componentes/ui/Cartao";
import { Campo, Rotulo, Selecao } from "@/componentes/ui/Controles";
import { EstadoErro, LinhasCarregando } from "@/componentes/ui/Estados";
import { Modal } from "@/componentes/ui/Modal";
import { Selo } from "@/componentes/ui/Selo";
import { Tabela, Td, Th, Tr } from "@/componentes/ui/Tabela";

const NOVA_LOJA = "__nova__";
const CHAVE_CADASTRO = ["cameras-cadastro"];

function useAtualizarCadastro() {
  const cliente = useQueryClient();
  return () => {
    void cliente.invalidateQueries({ queryKey: CHAVE_CADASTRO });
    void cliente.invalidateQueries({ queryKey: ["lojas"] });
  };
}

function UrlCopiavel({ url }: { url: string }) {
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success("URL copiada");
    } catch {
      toast.info("Clique na URL e use Ctrl+C para copiar");
    }
  };
  return (
    <div className="flex gap-2">
      <Campo readOnly value={url} onFocus={(e) => e.target.select()} className="w-full font-mono text-xs" />
      <Botao type="button" onClick={copiar} aria-label="Copiar URL">
        <Copy className="h-4 w-4" />
      </Botao>
    </div>
  );
}

function ResultadoCadastro({ criada }: { criada: CameraCriada }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-suave">
        No app da câmera, escolha <strong>RTMP personalizado</strong> e cole a URL abaixo. Ela já tem o usuário e a senha da câmera.
      </p>
      <UrlCopiavel url={criada.url} />
      {criada.roteador_ok ? (
        <Selo tom="sucesso">roteador configurado</Selo>
      ) : (
        <p className="text-xs text-atencao">
          A câmera foi salva, mas o roteador ainda não aceitou ({criada.erro_roteador}). O sistema tenta de novo a cada minuto.
        </p>
      )}
    </div>
  );
}

function NovaCamera({ dados, aoCriar }: { dados: CadastroCameras; aoCriar: (criada: CameraCriada) => void }) {
  const atualizar = useAtualizarCadastro();
  const [formulario, setFormulario] = useState({ codigo: "", descricao: "", loja: dados.lojas[0]?.id ?? NOVA_LOJA, nomeLoja: "", pdv: "" });
  const lojaNova = formulario.loja === NOVA_LOJA;
  const criar = useMutation({
    mutationFn: () =>
      enviar<CameraCriada>("/api/cameras/cadastro", "POST", {
        codigo: formulario.codigo,
        descricao: formulario.descricao,
        ...(lojaNova ? { nova_loja: { nome: formulario.nomeLoja, pdv: formulario.pdv } } : { loja: formulario.loja }),
      }),
    onSuccess: (criada) => {
      atualizar();
      aoCriar(criada);
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  const salvar = (evento: FormEvent) => {
    evento.preventDefault();
    criar.mutate();
  };
  return (
    <form onSubmit={salvar} className="space-y-4">
      <Rotulo texto="Código da câmera">
        <Campo required minLength={3} maxLength={40} pattern="[A-Za-z0-9_\-]+" placeholder="ex.: XTPRZS54" value={formulario.codigo} onChange={(e) => setFormulario({ ...formulario, codigo: e.target.value })} />
      </Rotulo>
      <Rotulo texto="Descrição (opcional)">
        <Campo placeholder="ex.: Santa Terezinha · entrada" value={formulario.descricao} onChange={(e) => setFormulario({ ...formulario, descricao: e.target.value })} />
      </Rotulo>
      <Rotulo texto="Loja">
        <Selecao value={formulario.loja} onChange={(e) => setFormulario({ ...formulario, loja: e.target.value })}>
          {dados.lojas.map((loja) => (
            <option key={loja.id} value={loja.id}>
              {loja.nome}
            </option>
          ))}
          <option value={NOVA_LOJA}>+ Nova loja</option>
        </Selecao>
      </Rotulo>
      {lojaNova && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Rotulo texto="Nome da loja">
            <Campo required minLength={2} value={formulario.nomeLoja} onChange={(e) => setFormulario({ ...formulario, nomeLoja: e.target.value })} />
          </Rotulo>
          <Rotulo texto="PDVs TouchPay (opcional, separados por vírgula)">
            <Campo inputMode="numeric" pattern="[0-9, ]*" placeholder="ex.: 1234, 5678" value={formulario.pdv} onChange={(e) => setFormulario({ ...formulario, pdv: e.target.value })} />
          </Rotulo>
        </div>
      )}
      <Botao variante="primaria" type="submit" className="w-full" disabled={criar.isPending}>
        Cadastrar e gerar URL
      </Botao>
    </form>
  );
}

const SO_DIGITOS = /^\d+$/;

function separarPdvs(valor: string) {
  return valor.split(",").map((pdv) => pdv.trim()).filter(Boolean);
}

function normalizar(texto: string) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function ordemDoPdv(pdv: PdvTouchPay, loja: LojaCadastro) {
  if (pdv.loja && pdv.loja !== loja.id) return 2;
  return normalizar(pdv.nome).includes(normalizar(loja.nome)) ? 0 : 1;
}

function CaixaMarcacao({ marcada }: { marcada: boolean }) {
  return (
    <span
      className={cn(
        "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
        marcada ? "border-primaria bg-primaria text-primaria-texto" : "border-borda bg-superficie",
      )}
    >
      {marcada && <Check className="h-3 w-3" strokeWidth={3} />}
    </span>
  );
}

function EtiquetaPdv({ id, nome, aoRemover }: { id: string; nome?: string; aoRemover?: () => void }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-primaria/10 py-1 pl-2 pr-1.5 text-xs text-primaria ring-1 ring-inset ring-primaria/20">
      <span className="font-semibold tabular-nums">{id}</span>
      {nome && <span className="truncate text-texto/80">{nome}</span>}
      {aoRemover && (
        <button type="button" onClick={aoRemover} className="foco rounded p-0.5 hover:bg-primaria/15" aria-label={`Tirar PDV ${id}`}>
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  );
}

function EditorPdvs({ loja, lojas, pdvs, listaIndisponivel, aoFechar }: {
  loja: LojaCadastro;
  lojas: LojaCadastro[];
  pdvs: PdvTouchPay[];
  listaIndisponivel: boolean;
  aoFechar: () => void;
}) {
  const atualizar = useAtualizarCadastro();
  const [selecionados, setSelecionados] = useState(() => separarPdvs(loja.pdv));
  const [busca, setBusca] = useState("");
  const nomeDoPdv = new Map(pdvs.map((pdv) => [pdv.id, pdv.nome]));
  const nomeDaLoja = new Map(lojas.map((item) => [item.id, item.nome]));
  const termo = normalizar(busca.trim());
  const encontrados = pdvs
    .filter((pdv) => !termo || normalizar(`${pdv.id} ${pdv.nome}`).includes(termo))
    .sort((a, b) => ordemDoPdv(a, loja) - ordemDoPdv(b, loja) || a.nome.localeCompare(b.nome));
  const numeroDigitado = busca.trim();
  const podeAdicionarManual = SO_DIGITOS.test(numeroDigitado) && !selecionados.includes(numeroDigitado) && !nomeDoPdv.has(numeroDigitado);
  const alterado = selecionados.join(",") !== separarPdvs(loja.pdv).join(",");

  const alternar = (id: string) =>
    setSelecionados((atuais) => (atuais.includes(id) ? atuais.filter((pdv) => pdv !== id) : [...atuais, id]));
  const adicionarManual = () => {
    setSelecionados((atuais) => [...atuais, numeroDigitado]);
    setBusca("");
  };
  const manterFocoNaBusca = (evento: MouseEvent) => evento.preventDefault();
  const teclarNaBusca = (evento: KeyboardEvent<HTMLInputElement>) => {
    if (evento.key !== "Enter") return;
    evento.preventDefault();
    if (podeAdicionarManual) adicionarManual();
    else if (encontrados.length === 1 && !(encontrados[0].loja && encontrados[0].loja !== loja.id)) alternar(encontrados[0].id);
  };

  const salvar = useMutation({
    mutationFn: () => enviar(`/api/cameras/lojas/${encodeURIComponent(loja.id)}/pdv`, "PUT", { pdv: selecionados.join(",") }),
    onSuccess: () => {
      atualizar();
      toast.success(selecionados.length ? `PDVs de ${loja.nome} salvos` : `${loja.nome} ficou sem PDV`);
      aoFechar();
    },
    onError: (erro: Error) => toast.error(erro.message),
  });

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-xs font-medium text-suave">
          {selecionados.length ? `${selecionados.length} selecionado${selecionados.length > 1 ? "s" : ""}` : "Nenhum PDV selecionado"}
        </p>
        <div className="flex min-h-9 flex-wrap gap-1.5 rounded-lg border border-dashed p-2">
          {selecionados.length ? (
            selecionados.map((id) => <EtiquetaPdv key={id} id={id} nome={nomeDoPdv.get(id)} aoRemover={() => alternar(id)} />)
          ) : (
            <span className="text-xs text-fraco">Marque abaixo os PDVs que ficam nesta loja</span>
          )}
        </div>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fraco" />
        <Campo
          autoFocus
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          onKeyDown={teclarNaBusca}
          placeholder={listaIndisponivel ? "Digite o número do PDV e aperte Enter" : "Buscar por número ou nome do PDV"}
          className="w-full pl-9"
        />
      </div>

      {listaIndisponivel && (
        <p className="rounded-lg bg-atencao/10 px-3 py-2 text-xs text-atencao">
          Não deu para carregar a lista da TouchPay. Digite o número de cada PDV e aperte Enter.
        </p>
      )}

      <ul className="rolagem -mx-1 max-h-72 space-y-0.5 overflow-y-auto p-1">
        {podeAdicionarManual && (
          <li>
            <button type="button" onMouseDown={manterFocoNaBusca} onClick={adicionarManual} className="foco flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-primaria hover:bg-primaria/10">
              <Plus className="h-4 w-4" /> Adicionar o PDV <span className="font-semibold tabular-nums">{numeroDigitado}</span>
            </button>
          </li>
        )}
        {encontrados.map((pdv) => {
          const marcado = selecionados.includes(pdv.id);
          const outraLoja = pdv.loja && pdv.loja !== loja.id ? nomeDaLoja.get(pdv.loja) ?? pdv.loja : null;
          return (
            <li key={pdv.id}>
              <button
                type="button"
                disabled={Boolean(outraLoja)}
                onMouseDown={manterFocoNaBusca}
                onClick={() => alternar(pdv.id)}
                aria-pressed={marcado}
                className={cn(
                  "foco flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                  outraLoja ? "cursor-not-allowed opacity-60" : "hover:bg-elevada",
                  marcado && "bg-primaria/5",
                )}
              >
                <CaixaMarcacao marcada={marcado} />
                <span className="w-12 shrink-0 text-xs font-semibold tabular-nums text-suave">{pdv.id}</span>
                <span className="min-w-0 flex-1 truncate text-sm">{pdv.nome}</span>
                {outraLoja && <Selo className="shrink-0">em {outraLoja}</Selo>}
              </button>
            </li>
          );
        })}
        {!encontrados.length && !podeAdicionarManual && !listaIndisponivel && (
          <li className="px-3 py-6 text-center text-sm text-fraco">Nenhum PDV encontrado para “{busca}”</li>
        )}
      </ul>

      <footer className="flex justify-end gap-2 border-t pt-4">
        <Botao variante="fantasma" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao variante="primaria" onClick={() => salvar.mutate()} disabled={!alterado || salvar.isPending}>
          <Save className="h-4 w-4" /> {salvar.isPending ? "Salvando…" : "Salvar"}
        </Botao>
      </footer>
    </div>
  );
}

function LinhaLoja({ loja, nomeDoPdv, aoEditar, aoAjustarRecorte, aoSalvarRecorte }: {
  loja: LojaCadastro;
  nomeDoPdv: Map<string, string>;
  aoEditar: () => void;
  aoAjustarRecorte: () => void;
  aoSalvarRecorte: () => void;
}) {
  const salvos = separarPdvs(loja.pdv);
  return (
    <Tr>
      <Td className="w-48 font-medium">{loja.nome}</Td>
      <Td>
        {salvos.length ? (
          <div className="flex flex-wrap gap-1.5">
            {salvos.map((id) => (
              <EtiquetaPdv key={id} id={id} nome={nomeDoPdv.get(id)} />
            ))}
          </div>
        ) : (
          <Selo tom="atencao">
            <AlertTriangle className="h-3 w-3" /> Sem PDV: a IA não confere o pagamento
          </Selo>
        )}
      </Td>
      <Td className="w-52">
        <SituacaoRecorte loja={loja} aoSalvar={aoSalvarRecorte} aoAjustar={aoAjustarRecorte} />
      </Td>
      <Td className="w-40 text-right">
        <Botao tamanho="sm" variante={salvos.length ? "secundaria" : "primaria"} onClick={aoEditar}>
          {salvos.length ? <Pencil className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {salvos.length ? "Editar PDVs" : "Escolher PDVs"}
        </Botao>
      </Td>
    </Tr>
  );
}

function LojasEPdv({ lojas }: { lojas: LojaCadastro[] }) {
  const [editando, setEditando] = useState<LojaCadastro | null>(null);
  const [configurandoRecorte, setConfigurandoRecorte] = useState<LojaCadastro | null>(null);
  const atualizar = useAtualizarCadastro();
  const { data: pdvs = [], isError, isLoading } = useQuery({
    queryKey: ["pdvs-touchpay"],
    queryFn: () => api<PdvTouchPay[]>("/api/cameras/pdvs-touchpay"),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const nomeDoPdv = new Map(pdvs.map((pdv) => [pdv.id, pdv.nome]));
  const comPdv = lojas.filter((loja) => separarPdvs(loja.pdv).length).length;
  return (
    <Cartao className="mt-6">
      <CabecalhoCartao
        titulo="Lojas"
        descricao="Os PDVs TouchPay são onde a IA procura o pagamento de cada visita. Entrada sem compra abre ocorrência para revisão de quem entra e sai sem comprar."
        acoes={
          <Selo tom={comPdv === lojas.length ? "sucesso" : "atencao"}>
            {comPdv} de {lojas.length} lojas com PDV
          </Selo>
        }
      />
      <Tabela>
        <thead>
          <tr>
            <Th>Loja</Th>
            <Th>PDVs</Th>
            <Th>Entrada sem compra</Th>
            <Th className="text-right">Ações</Th>
          </tr>
        </thead>
        <tbody>
          {lojas.map((loja) => (
            <LinhaLoja
              key={loja.id}
              loja={loja}
              nomeDoPdv={nomeDoPdv}
              aoEditar={() => setEditando(loja)}
              aoAjustarRecorte={() => setConfigurandoRecorte(loja)}
              aoSalvarRecorte={atualizar}
            />
          ))}
        </tbody>
      </Tabela>
      <Modal aberto={Boolean(editando)} titulo={editando ? `PDVs de ${editando.nome}` : ""} aoFechar={() => setEditando(null)} className="max-w-lg">
        {editando &&
          (isLoading ? (
            <LinhasCarregando />
          ) : (
            <EditorPdvs loja={editando} lojas={lojas} pdvs={pdvs} listaIndisponivel={isError || !pdvs.length} aoFechar={() => setEditando(null)} />
          ))}
      </Modal>
      <Modal
        aberto={Boolean(configurandoRecorte)}
        titulo={configurandoRecorte ? `Entrada sem compra · ${configurandoRecorte.nome}` : ""}
        aoFechar={() => setConfigurandoRecorte(null)}
        className="max-w-md"
      >
        {configurandoRecorte && (
          <EditorRecorteSemCompra loja={configurandoRecorte} aoSalvar={atualizar} aoFechar={() => setConfigurandoRecorte(null)} />
        )}
      </Modal>
    </Cartao>
  );
}

function SituacaoMaquininha({ camera, aoMarcar }: { camera: CameraCadastro; aoMarcar: () => void }) {
  const quantidade = camera.maquininhas?.length ?? 0;
  const definidaPeloAdmin = camera.maquininhas !== null;
  return (
    <div className="flex items-center gap-2">
      {quantidade ? (
        <Selo tom="sucesso">{quantidade > 1 ? `${quantidade} marcadas` : "marcada"}</Selo>
      ) : definidaPeloAdmin ? (
        <Selo tom="atencao">sem maquininha</Selo>
      ) : (
        <Selo>automática</Selo>
      )}
      <Botao tamanho="sm" variante="fantasma" onClick={aoMarcar} aria-label={`Marcar maquininha de ${camera.descricao}`}>
        {definidaPeloAdmin ? <Pencil className="h-3.5 w-3.5" /> : <Scan className="h-3.5 w-3.5" />}
        {definidaPeloAdmin ? "Editar" : "Marcar"}
      </Botao>
    </div>
  );
}

function LinhaCamera({ camera, aoRemover, aoMarcar }: {
  camera: CameraCadastro;
  aoRemover: (camera: CameraCadastro) => void;
  aoMarcar: (camera: CameraCadastro) => void;
}) {
  return (
    <Tr>
      <Td>
        <p className="font-medium">{camera.descricao}</p>
        <p className="font-mono text-xs text-fraco">{camera.caminho}</p>
      </Td>
      <Td>{camera.loja_nome}</Td>
      <Td>{camera.cadastrada ? <Selo tom="info">painel</Selo> : <Selo>arquivo de config</Selo>}</Td>
      <Td>
        <SituacaoMaquininha camera={camera} aoMarcar={() => aoMarcar(camera)} />
      </Td>
      <Td className="min-w-72">{camera.url ? <UrlCopiavel url={camera.url} /> : <span className="text-xs text-fraco">definida no roteador.yml</span>}</Td>
      <Td className="text-right">
        {camera.cadastrada && (
          <Botao tamanho="sm" variante="fantasma" onClick={() => aoRemover(camera)} aria-label={`Remover ${camera.nome}`}>
            <Trash2 className="h-3.5 w-3.5" />
          </Botao>
        )}
      </Td>
    </Tr>
  );
}

export function Cameras() {
  const atualizar = useAtualizarCadastro();
  const [criando, setCriando] = useState(false);
  const [criada, setCriada] = useState<CameraCriada | null>(null);
  const [marcando, setMarcando] = useState<CameraCadastro | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: CHAVE_CADASTRO, queryFn: () => api<CadastroCameras>("/api/cameras/cadastro") });
  const remover = useMutation({
    mutationFn: (camera: CameraCadastro) => enviar(`/api/cameras/cadastro/${encodeURIComponent(camera.nome)}`, "DELETE"),
    onSuccess: () => {
      atualizar();
      toast.success("Câmera removida");
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
  const confirmarRemocao = (camera: CameraCadastro) => {
    if (window.confirm(`Remover a câmera ${camera.descricao}? Ela deixa de ser aceita pelo roteador.`)) remover.mutate(camera);
  };
  const fecharCadastro = () => {
    setCriando(false);
    setCriada(null);
  };
  const fecharMarcacao = () => {
    setMarcando(null);
    atualizar();
  };

  return (
    <>
      <CabecalhoPagina
        titulo="Câmeras"
        descricao="Cadastre câmeras novas e pegue a URL RTMP para configurar no app"
        acoes={
          <Botao variante="primaria" onClick={() => setCriando(true)} disabled={!data}>
            <Plus className="h-4 w-4" /> Nova câmera
          </Botao>
        }
      />
      {data && !data.roteador.disponivel && <EstadoErro mensagem="Este ambiente não tem acesso à API do roteador: as câmeras cadastradas não serão aceitas." />}
      {data?.roteador.erro && data.roteador.disponivel && <EstadoErro mensagem={`Roteador: ${data.roteador.erro}`} />}
      {data && !data.rtmp_publico_configurado && (
        <p className="mb-4 text-xs text-atencao">VIGIA_RTMP_PUBLICO não está definido: troque IP_DO_SERVIDOR na URL pelo IP público do servidor.</p>
      )}
      <Cartao>
        {isLoading && <LinhasCarregando />}
        {error && <EstadoErro mensagem={error.message} />}
        {data && (
          <Tabela>
            <thead>
              <tr>
                <Th>Câmera</Th>
                <Th>Loja</Th>
                <Th>Origem</Th>
                <Th>Maquininha</Th>
                <Th>URL RTMP</Th>
                <Th className="text-right">Ações</Th>
              </tr>
            </thead>
            <tbody>
              {data.cameras.map((camera) => (
                <LinhaCamera key={camera.nome} camera={camera} aoRemover={confirmarRemocao} aoMarcar={setMarcando} />
              ))}
            </tbody>
          </Tabela>
        )}
      </Cartao>
      {data?.roteador.sincronizado_em && <p className="mt-3 text-xs text-fraco">Roteador conferido {haQuantoTempo(data.roteador.sincronizado_em)}</p>}
      {data && <LojasEPdv lojas={data.lojas} />}
      <Modal aberto={Boolean(marcando)} titulo={marcando ? `Maquininha · ${marcando.descricao}` : ""} aoFechar={fecharMarcacao} className="max-h-[96vh] max-w-6xl overflow-y-auto">
        {marcando && <EditorMaquininhas camera={marcando} aoFechar={fecharMarcacao} />}
      </Modal>
      <Modal aberto={criando} titulo={criada ? "Câmera cadastrada" : "Nova câmera"} aoFechar={fecharCadastro}>
        {criada ? <ResultadoCadastro criada={criada} /> : data && <NovaCamera dados={data} aoCriar={setCriada} />}
      </Modal>
    </>
  );
}
