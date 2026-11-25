import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Clock, DoorOpen, Film, Save, ShieldAlert } from "lucide-react";
import { enviar } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { LojaCadastro, RecorteSemCompra } from "@/lib/tipos";
import { Botao } from "../ui/Botao";
import { Campo } from "../ui/Controles";

const ESPERAS_SUGERIDAS_MIN = [2, 5, 10, 15];
const ESPERA_MINIMA_MIN = 1;
const ESPERA_MAXIMA_MIN = 60;

const emMinutos = (segundos: number) => Math.round(segundos / 60);
const esperaValida = (minutos: number) => Number.isInteger(minutos) && minutos >= ESPERA_MINIMA_MIN && minutos <= ESPERA_MAXIMA_MIN;

function useSalvarRecorte(loja: LojaCadastro, aoSalvar: () => void) {
  return useMutation({
    mutationFn: ({ ativo, espera_min }: { ativo: boolean; espera_min: number }) =>
      enviar<{ recorte_sem_compra: RecorteSemCompra }>(`/api/cameras/lojas/${encodeURIComponent(loja.id)}/recorte-sem-compra`, "PUT", { ativo, espera_min }),
    onSuccess: ({ recorte_sem_compra: { ativo } }) => {
      aoSalvar();
      toast.success(ativo ? `${loja.nome}: quem entrar e sair sem comprar vira ocorrência` : `${loja.nome}: recorte de entrada sem compra desligado`);
    },
    onError: (erro: Error) => toast.error(erro.message),
  });
}

export function Interruptor({ ligado, aoMudar, rotulo, desabilitado }: {
  ligado: boolean;
  aoMudar: (ligado: boolean) => void;
  rotulo: string;
  desabilitado?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      aria-label={rotulo}
      disabled={desabilitado}
      onClick={() => aoMudar(!ligado)}
      className={cn(
        "foco box-border inline-flex h-5 w-9 shrink-0 items-center rounded-full border-0 p-0.5 transition-colors duration-200 disabled:cursor-wait disabled:opacity-60",
        ligado ? "bg-revisao" : "bg-borda",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm ring-1 ring-black/5 transition-transform duration-200",
          ligado ? "translate-x-4" : "translate-x-0",
        )}
      />
    </button>
  );
}

export function SituacaoRecorte({ loja, aoSalvar, aoAjustar }: { loja: LojaCadastro; aoSalvar: () => void; aoAjustar: () => void }) {
  const { ativo, espera_s } = loja.recorte_sem_compra;
  const salvar = useSalvarRecorte(loja, aoSalvar);
  const semPdv = ativo && !loja.pdv;
  return (
    <div className="flex items-center gap-3">
      <Interruptor
        ligado={ativo}
        desabilitado={salvar.isPending}
        aoMudar={(ligado) => salvar.mutate({ ativo: ligado, espera_min: emMinutos(espera_s) })}
        rotulo={`Recortar entradas sem compra em ${loja.nome}`}
      />
      <div className="leading-tight">
        <p className={cn("text-sm", ativo ? "font-medium text-revisao" : "text-suave")}>
          {ativo ? "Ligado" : "Desligado"}
          {semPdv && <span className="ml-1.5 text-xs font-normal text-atencao">· sem PDV</span>}
        </p>
        <button type="button" onClick={aoAjustar} className="foco rounded text-xs text-fraco underline-offset-2 hover:text-texto hover:underline">
          {ativo ? `espera ${emMinutos(espera_s)} min · ajustar` : "como funciona"}
        </button>
      </div>
    </div>
  );
}

function Passo({ icone: Icone, children }: { icone: typeof Clock; children: string }) {
  return (
    <li className="flex gap-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-revisao/10 text-revisao">
        <Icone className="h-3.5 w-3.5" />
      </span>
      <span className="pt-0.5">{children}</span>
    </li>
  );
}

function EscolhaDeEspera({ minutos, aoMudar, desabilitada }: { minutos: number; aoMudar: (minutos: number) => void; desabilitada: boolean }) {
  const [personalizada, setPersonalizada] = useState(!ESPERAS_SUGERIDAS_MIN.includes(minutos));
  const opcao = (ativa: boolean) =>
    cn(
      "foco h-8 rounded-lg border px-3 text-sm tabular-nums transition-colors disabled:cursor-not-allowed",
      ativa ? "border-revisao bg-revisao/10 font-medium text-revisao" : "text-suave hover:bg-elevada",
    );
  return (
    <fieldset disabled={desabilitada} className="space-y-2 disabled:opacity-50">
      <legend className="mb-2 text-sm font-medium">Esperar a compra por</legend>
      <div className="flex flex-wrap items-center gap-1.5">
        {ESPERAS_SUGERIDAS_MIN.map((sugestao) => (
          <button
            key={sugestao}
            type="button"
            className={opcao(!personalizada && minutos === sugestao)}
            onClick={() => {
              setPersonalizada(false);
              aoMudar(sugestao);
            }}
          >
            {sugestao} min
          </button>
        ))}
        <button type="button" className={opcao(personalizada)} onClick={() => setPersonalizada(true)}>
          Outro
        </button>
        {personalizada && (
          <span className="flex items-center gap-1.5 text-sm text-suave">
            <Campo
              autoFocus
              type="number"
              inputMode="numeric"
              min={ESPERA_MINIMA_MIN}
              max={ESPERA_MAXIMA_MIN}
              value={Number.isNaN(minutos) ? "" : minutos}
              onChange={(e) => aoMudar(e.target.valueAsNumber)}
              aria-label="Minutos de espera"
              className="h-8 w-20"
            />
            min
          </span>
        )}
      </div>
      <p className={cn("text-xs", esperaValida(minutos) ? "text-fraco" : "text-alerta")}>
        {esperaValida(minutos)
          ? "Compra que aparecer nesse tempo depois da saída conta como compra e não gera ocorrência."
          : `Escolha de ${ESPERA_MINIMA_MIN} a ${ESPERA_MAXIMA_MIN} minutos.`}
      </p>
    </fieldset>
  );
}

export function EditorRecorteSemCompra({ loja, aoSalvar, aoFechar }: { loja: LojaCadastro; aoSalvar: () => void; aoFechar: () => void }) {
  const [ativo, setAtivo] = useState(loja.recorte_sem_compra.ativo);
  const [minutos, setMinutos] = useState(emMinutos(loja.recorte_sem_compra.espera_s));
  const salvar = useSalvarRecorte(loja, () => {
    aoSalvar();
    aoFechar();
  });
  const alterado = ativo !== loja.recorte_sem_compra.ativo || minutos !== emMinutos(loja.recorte_sem_compra.espera_s);

  const enviarFormulario = (evento: FormEvent) => {
    evento.preventDefault();
    if (esperaValida(minutos)) salvar.mutate({ ativo, espera_min: minutos });
  };

  return (
    <form onSubmit={enviarFormulario} className="space-y-5">
      <ol className="space-y-2.5 text-sm text-suave">
        <Passo icone={DoorOpen}>Alguém entra na loja e sai.</Passo>
        <Passo icone={Clock}>O Vigia espera a compra aparecer na TouchPay.</Passo>
        <Passo icone={Film}>Sem compra, abre uma ocorrência com o vídeo da visita para a equipe revisar.</Passo>
      </ol>

      <label className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border p-3.5">
        <span>
          <span className="block text-sm font-medium">Recortar entradas sem compra</span>
          <span className="block text-xs text-suave">Use em lojas onde não é comum entrar sem comprar.</span>
        </span>
        <Interruptor ligado={ativo} aoMudar={setAtivo} rotulo="Recortar entradas sem compra" />
      </label>

      <EscolhaDeEspera minutos={minutos} aoMudar={setMinutos} desabilitada={!ativo} />

      {ativo && !loja.pdv && (
        <p className="flex gap-2 rounded-lg bg-atencao/10 px-3 py-2 text-xs text-atencao">
          <ShieldAlert className="h-4 w-4 shrink-0" /> Esta loja não tem PDV: o Vigia não acha nenhuma compra e toda visita vira ocorrência.
        </p>
      )}

      <footer className="flex justify-end gap-2 border-t pt-4">
        <Botao type="button" variante="fantasma" onClick={aoFechar}>
          Cancelar
        </Botao>
        <Botao type="submit" variante="primaria" disabled={!alterado || !esperaValida(minutos) || salvar.isPending}>
          <Save className="h-4 w-4" /> {salvar.isPending ? "Salvando…" : "Salvar"}
        </Botao>
      </footer>
    </form>
  );
}
