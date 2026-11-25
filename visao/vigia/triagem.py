import base64
import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal

import anthropic
import cv2
import openai
from pydantic import BaseModel, ValidationError

from .config import nome_da_loja
from .fusao import aviso_de_ocorrencia
from .linha_do_tempo import linha_do_tempo

log = logging.getLogger(__name__)

BETA_FALLBACK = "server-side-fallback-2026-07-01"
PREFIXO_MODELOS_SEM_FALLBACK = "claude-haiku"
MAX_TOKENS = 16000
INTERVALO_VERIFICACAO_S = 5
QUALIDADE_JPEG = 85
JANELA_VENDAS_S = 600
ROTULOS_FOTO = {"pessoa": "pessoa em destaque", "totem": "pessoa no totem"}

INSTRUCOES = """Você faz a triagem de ocorrências de uma loja autônoma: não há funcionários, o cliente pega o produto e paga sozinho no totem (maquininha de cartão) ou pelo app.

Um detector de visão computacional acompanha cada pessoa nas câmeras. Ele abriu esta ocorrência porque achou que a pessoa pegou um produto e não encontrou pagamento aprovado na TouchPay, o sistema de vendas da loja. O detector erra bastante: confunde celular, carteira, sacola ou objeto do próprio cliente com produto, conta como cliente o repositor que abastece a geladeira, perde a pessoa quando ela passa no totem e às vezes casa o pagamento com a pessoa errada.

Seu papel é ser um filtro antes do operador humano. Olhe as fotos e os quadros do vídeo, leia os dados do detector e diga o que as imagens mostram:
- furto_provavel: dá para ver a pessoa com um produto da loja e nada nas imagens indica pagamento (não usa o totem nem o celular para pagar, esconde o produto, sai com ele).
- falso_positivo: as imagens mostram que o detector errou. Por exemplo: o objeto na mão é do próprio cliente; a pessoa devolve o produto; ela paga no totem ou no app; é reposição de estoque; não há produto de verdade.
- inconclusivo: as imagens não bastam para decidir (ângulo ruim, imagem escura, a pessoa sai do quadro, o momento importante não aparece).

Regras:
- Na dúvida entre falso_positivo e as outras opções, escolha inconclusivo. Um falso_positivo com confiança alta tira a ocorrência da fila humana, e um furto escondido custa mais caro que uma revisão a mais.
- A confiança vai de 0 a 100 e mede o quanto as imagens sustentam o seu veredito, não o score do detector.
- Nas fotos do detector, o retângulo maior marca a pessoa e o retângulo com a palavra "produto" marca o que ele achou que é produto.
- O resumo é para o operador: uma ou duas frases em português, dizendo o que se vê e por que você chegou ao veredito.
- Em sinais, liste de 2 a 6 observações curtas e concretas das imagens.
- A justificativa explica o seu raciocínio para o operador em 2 a 5 frases: quais imagens e momentos pesaram na decisão (cite a câmera e o quadro), o que confirma ou contradiz o detector e as vendas da TouchPay, e por que não escolheu os outros vereditos.
- Descreva ações e objetos. Não descreva traços físicos, roupa nem nada que identifique a pessoa além do necessário para separá-la de outra."""

ESQUEMA_PARECER = {
    "type": "object",
    "properties": {
        "veredito": {"type": "string", "enum": ["furto_provavel", "falso_positivo", "inconclusivo"]},
        "confianca": {"type": "integer"},
        "resumo": {"type": "string"},
        "sinais": {"type": "array", "items": {"type": "string"}},
        "justificativa": {"type": "string"},
    },
    "required": ["veredito", "confianca", "resumo", "sinais", "justificativa"],
    "additionalProperties": False,
}


class ViaAnthropic:
    chave = "ANTHROPIC_API_KEY"
    erros = (anthropic.APIError,)

    def __init__(self, p, cliente=None):
        self.p = p
        self.cliente = cliente or anthropic.Anthropic()

    def _conteudo(self, partes):
        return [{"type": "text", "text": valor} if tipo == "texto" else
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": valor}}
                for tipo, valor in partes]

    def analisar(self, partes):
        modelo = self.p["modelo"]
        extras = {} if modelo.startswith(PREFIXO_MODELOS_SEM_FALLBACK) else {"betas": [BETA_FALLBACK], "fallbacks": "default"}
        resposta = self.cliente.beta.messages.create(
            model=modelo,
            max_tokens=MAX_TOKENS,
            system=INSTRUCOES,
            output_config={"effort": self.p["esforco"], "format": {"type": "json_schema", "schema": ESQUEMA_PARECER}},
            messages=[{"role": "user", "content": self._conteudo(partes)}],
            **extras,
        )
        if resposta.stop_reason == "refusal":
            raise RespostaInvalida("a IA recusou a análise")
        if resposta.stop_reason == "max_tokens":
            raise RespostaInvalida("a resposta da IA veio cortada")
        return next((bloco.text for bloco in resposta.content if bloco.type == "text"), ""), resposta.model


class ViaOpenAI:
    chave = "OPENAI_API_KEY"
    erros = (openai.APIError,)

    def __init__(self, p, cliente=None):
        self.p = p
        self.cliente = cliente or openai.OpenAI()

    def _conteudo(self, partes):
        return [{"type": "text", "text": valor} if tipo == "texto" else
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{valor}", "detail": "high"}}
                for tipo, valor in partes]

    def analisar(self, partes):
        extras = {"reasoning_effort": self.p["esforco"]} if self.p.get("esforco") else {}
        resposta = self.cliente.chat.completions.create(
            model=self.p["modelo"],
            max_completion_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": INSTRUCOES},
                      {"role": "user", "content": self._conteudo(partes)}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "parecer", "strict": True, "schema": ESQUEMA_PARECER}},
            **extras,
        )
        escolha = resposta.choices[0]
        if escolha.message.refusal:
            raise RespostaInvalida(f"a IA recusou a análise: {escolha.message.refusal}")
        if escolha.finish_reason == "length":
            raise RespostaInvalida("a resposta da IA veio cortada")
        return escolha.message.content or "", resposta.model


PROVEDORES = {"openai": ViaOpenAI, "anthropic": ViaAnthropic}
ERROS_DAS_APIS = tuple(erro for provedor in PROVEDORES.values() for erro in provedor.erros)


class Parecer(BaseModel):
    veredito: Literal["furto_provavel", "falso_positivo", "inconclusivo"]
    confianca: int
    resumo: str
    sinais: list[str]
    justificativa: str


class RespostaInvalida(Exception):
    pass


class SemImagens(Exception):
    pass


def quadros_do_clipe(caminho, quantidade):
    video = cv2.VideoCapture(str(caminho))
    try:
        total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS) or 0
        quadros = []
        for indice in range(quantidade if total > 0 else 0):
            posicao = int((indice + 0.5) * total / quantidade)
            video.set(cv2.CAP_PROP_POS_FRAMES, posicao)
            lido, quadro = video.read()
            if lido:
                quadros.append((posicao / fps if fps else None, quadro))
        return quadros
    finally:
        video.release()


def descrever_foto(caminho):
    camera = caminho.parent.name
    rotulo = caminho.stem.rsplit("_", 1)[-1]
    if rotulo.startswith("pegou"):
        return f"Foto do detector, câmera {camera}: momento em que viu produto na mão ({rotulo.removeprefix('pegou')}º item)"
    return f"Foto do detector, câmera {camera}: {ROTULOS_FOTO.get(rotulo, rotulo)}"


def segundos(valor):
    return f"{valor:.0f}s"


class Triagem:
    def __init__(self, cfg, banco, notificar, cliente=None):
        self.p = cfg.get("triagem_ia") or {}
        self.cfg = cfg
        self.banco = banco
        self.notificar = notificar
        self.raiz = Path(cfg["dados"]["evidencias"])
        self.provedor = self._criar_provedor(cliente)
        self.ativa = bool(self.p.get("ativa") and self.provedor)
        self.tentativas = {}
        self.proxima_tentativa = {}
        self.contagem = {"analisadas": 0, "encaminhadas": 0, "descartadas": 0, "erros": 0}
        self.ultimo_erro = ""
        self._parar = threading.Event()

    def _criar_provedor(self, cliente):
        if not self.p.get("ativa"):
            return None
        classe = PROVEDORES.get(self.p.get("provedor", "openai"))
        if not classe:
            log.warning("triagem por IA com provedor desconhecido %r: use %s", self.p.get("provedor"), " ou ".join(PROVEDORES))
            return None
        if cliente:
            return classe(self.p, cliente)
        if not os.environ.get(classe.chave):
            log.warning("triagem por IA ligada sem %s em config/.env: ocorrências vão direto para revisão humana", classe.chave)
            return None
        return classe(self.p)

    def aceita(self, resultado):
        return self.ativa and (resultado.get("score") or 0) > self.p.get("score_acima_de", 0)

    def iniciar(self):
        if not self.ativa:
            for ocorrencia in self.banco.ocorrencias_em_triagem():
                self._concluir(ocorrencia, {"situacao": "desligada"})
            return self
        log.info("triagem por IA ligada (%s, %s)", self.p.get("provedor", "openai"), self.p["modelo"])
        threading.Thread(target=self._rodar, name="triagem", daemon=True).start()
        return self

    def parar(self):
        self._parar.set()

    def _rodar(self):
        while not self._parar.wait(INTERVALO_VERIFICACAO_S):
            self.processar_pendentes(time.time())

    def processar_pendentes(self, agora):
        for ocorrencia in self.banco.ocorrencias_em_triagem():
            if self._pronta(ocorrencia, agora):
                self.triar(ocorrencia, agora)

    def _pronta(self, ocorrencia, agora):
        if self.proxima_tentativa.get(ocorrencia["id"], 0) > agora:
            return False
        clipes_completos = len(ocorrencia["clipes"]) >= len(ocorrencia["cameras"])
        return clipes_completos or agora >= ocorrencia["criada_em"] + self.p["espera_clipe_s"]

    def triar(self, ocorrencia, agora):
        try:
            parecer = self.avaliar(ocorrencia)
        except SemImagens:
            self._concluir(ocorrencia, {"situacao": "sem_imagens"})
            return
        except (*ERROS_DAS_APIS, RespostaInvalida) as erro:
            self._registrar_erro(ocorrencia, erro, agora)
            return
        self.contagem["analisadas"] += 1
        log.info("triagem da ocorrência %s: %s (%s%%)", ocorrencia["id"], parecer["veredito"], parecer["confianca"])
        self._concluir(ocorrencia, parecer)

    def _registrar_erro(self, ocorrencia, erro, agora):
        self.contagem["erros"] += 1
        self.ultimo_erro = str(erro)
        tentativas = self.tentativas.get(ocorrencia["id"], 0) + 1
        self.tentativas[ocorrencia["id"]] = tentativas
        log.warning("triagem da ocorrência %s falhou (%s/%s): %s", ocorrencia["id"], tentativas, self.p["tentativas"], erro)
        if tentativas >= self.p["tentativas"]:
            self._concluir(ocorrencia, {"situacao": "erro", "erro": str(erro)})
        else:
            self.proxima_tentativa[ocorrencia["id"]] = agora + self.p["intervalo_tentativas_s"]

    def _descartar(self, parecer):
        return (parecer.get("veredito") == "falso_positivo" and bool(self.p.get("descartar_falso_positivo"))
                and parecer["confianca"] >= self.p["confianca_descarte"])

    def _concluir(self, ocorrencia, parecer):
        self.tentativas.pop(ocorrencia["id"], None)
        self.proxima_tentativa.pop(ocorrencia["id"], None)
        situacao = "descartada" if self._descartar(parecer) else "aberta"
        atual = self.banco.concluir_triagem(ocorrencia["id"], parecer, situacao)
        if not atual or atual["situacao"] != situacao:
            return
        if situacao == "descartada":
            self.contagem["descartadas"] += 1
            self.notificar("ocorrencia_descartada", {"id": atual["id"], "resumo": parecer["resumo"]})
            return
        self.contagem["encaminhadas"] += 1
        motivo = f"IA: {parecer['resumo']}" if parecer.get("resumo") else None
        self.notificar("ocorrencia", aviso_de_ocorrencia(atual["id"], atual, atual["evidencias"], motivo))

    def avaliar(self, ocorrencia):
        partes = self._imagens(ocorrencia)
        if not partes:
            raise SemImagens()
        texto, modelo = self.provedor.analisar([*partes, ("texto", self._contexto(ocorrencia))])
        try:
            parecer = Parecer.model_validate_json(texto)
        except ValidationError as erro:
            raise RespostaInvalida("a resposta da IA veio fora do formato") from erro
        return {**parecer.model_dump(), "confianca": max(0, min(100, parecer.confianca)), "situacao": "concluida",
                "modelo": modelo, "analisada_em": time.time(), "imagens": sum(tipo == "imagem" for tipo, _ in partes)}

    def _imagem(self, quadro):
        altura, largura = quadro.shape[:2]
        escala = min(1.0, self.p["lado_maximo_px"] / max(altura, largura))
        if escala < 1:
            quadro = cv2.resize(quadro, (round(largura * escala), round(altura * escala)), interpolation=cv2.INTER_AREA)
        _, dados = cv2.imencode(".jpg", quadro, [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_JPEG])
        return "imagem", base64.standard_b64encode(dados.tobytes()).decode()

    def _imagens(self, ocorrencia):
        blocos = []
        for relativo in ocorrencia["evidencias"][: self.p["max_fotos"]]:
            caminho = self.raiz / relativo
            quadro = cv2.imread(str(caminho))
            if quadro is not None:
                blocos += [("texto", descrever_foto(caminho)), self._imagem(quadro)]
        for relativo in ocorrencia["clipes"][: self.p["max_clipes"]]:
            caminho = self.raiz / relativo
            camera = caminho.stem.split("_", 1)[-1]
            quadros = quadros_do_clipe(caminho, self.p["quadros_por_clipe"])
            for numero, (instante, quadro) in enumerate(quadros, 1):
                quando = f", {segundos(instante)} após o início do vídeo" if instante is not None else ""
                blocos += [("texto", f"Vídeo da câmera {camera}, quadro {numero} de {len(quadros)}{quando}"),
                           self._imagem(quadro)]
        return blocos

    def _vendas_proximas(self, ocorrencia):
        vendas = [p for p in self.banco.pagamentos_entre(ocorrencia["inicio"] - JANELA_VENDAS_S, ocorrencia["fim"] + JANELA_VENDAS_S)
                  if p["loja"] == ocorrencia["loja"]]
        if not vendas:
            return "- nenhuma"
        linhas = []
        for venda in vendas:
            itens = ", ".join(f"{i['quantidade']}x {i['descricao']}" for i in venda["itens"]) or f"{venda['qtd_itens'] or '?'} item(ns)"
            relativo = venda["horario"] - ocorrencia["inicio"]
            linhas.append(f"- {segundos(relativo)} em relação à entrada: {venda['situacao']}, R$ {venda['valor'] or 0:.2f}, {itens}")
        return "\n".join(linhas)

    def _contexto(self, ocorrencia):
        visita = self.banco.visita(ocorrencia["visita_id"]) or {}
        motivos = "\n".join(f"- {m['texto']} (peso {m['peso']})" for m in ocorrencia["motivos"])
        eventos = "\n".join(f"- {segundos(e['t'] - ocorrencia['inicio'])}: {e['texto']} ({e['camera']})"
                            for e in linha_do_tempo(visita))
        return f"""Dados do detector para esta ocorrência:
Loja: {nome_da_loja(self.cfg, ocorrencia['loja'])}
Câmeras: {', '.join(ocorrencia['cameras'])}
Tempo na loja: {segundos(ocorrencia['fim'] - ocorrencia['inicio'])}
Nível: {ocorrencia['nivel']} (score {ocorrencia['score']} de 100)
Vezes que viu produto na mão: {visita.get('pegadas', '?')}
Passou no totem segundo o detector: {'sim' if visita.get('foi_totem') else 'não'}

Por que o detector marcou:
{motivos}

Linha do tempo (segundos desde a entrada):
{eventos or '- sem eventos'}

Vendas da loja de 10 min antes a 10 min depois (TouchPay):
{self._vendas_proximas(ocorrencia)}

Dê o seu parecer."""

    def status(self):
        return {"ativa": self.ativa, "provedor": self.p.get("provedor", "openai"), "modelo": self.p.get("modelo"),
                "score_acima_de": self.p.get("score_acima_de", 0), "na_fila": len(self.banco.ocorrencias_em_triagem()),
                **self.contagem, "ultimo_erro": self.ultimo_erro}
