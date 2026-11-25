import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import pdvs_da_loja, recorte_sem_compra
from .deteccao.analise import semelhanca
from .touchpay import METODOS_APP

log = logging.getLogger(__name__)

INTERVALO_REVISAO_S = 30
MAX_FRAGMENTOS = 4
MIN_PEGADAS_VARIAS = 3
NIVEIS_DE_OCORRENCIA = ("alerta", "atencao")


def aviso_de_ocorrencia(ocorrencia_id, registro, evidencias, motivo=None):
    return {"id": ocorrencia_id, "loja": registro.get("loja"), "cameras": registro["cameras"], "nivel": registro["nivel"],
            "score": registro["score"], "motivo": motivo or registro["motivos"][0]["texto"],
            "evidencia": evidencias[0] if evidencias else None}


@dataclass(eq=False)
class Visita:
    id: str
    loja: str = None
    partes: list = field(default_factory=list)
    resultado: dict = None

    @property
    def inicio(self):
        return min(p.inicio for p in self.partes)

    @property
    def fim(self):
        return max(p.fim for p in self.partes)

    @property
    def cameras(self):
        return sorted({p.camera for p in self.partes})

    @property
    def hist(self):
        hists = [p.hist for p in self.partes if p.hist is not None]
        return sum(hists) / len(hists) if hists else None

    def pegadas(self, janela_s):
        contadas = []
        for t, camera in sorted((t, p.camera) for p in self.partes for t in p.pegadas):
            if not any(abs(t - tc) <= janela_s and cc != camera for tc, cc in contadas):
                contadas.append((t, camera))
        return len(contadas)

    @property
    def totem(self):
        return sorted((inicio, fim) for p in self.partes for inicio, fim in p.totem)

    @property
    def referencia_pagamento(self):
        return self.totem[-1][1] if self.totem else self.fim

    @property
    def fragmentos(self):
        return sum(len(p.ids_rastreador) for p in self.partes)

    @property
    def produto_s(self):
        tempos = [p.produto_s for p in self.partes if p.produto_s is not None]
        return sum(tempos) if tempos else None

    @property
    def saiu_com_produto(self):
        return any(p.saiu_com_produto for p in self.partes)

    @property
    def objeto_proprio(self):
        return any(p.objetos_proprios for p in self.partes)


def avaliar(*, pegadas, foi_totem, totem_coberto, pagamento, duracao, fragmentos, grupo_pagou, reposicao, f,
            pdv_conhecido=True, produto_s=None, saiu_com_produto=False, objeto_proprio=False):
    pesos, motivos = f["pesos"], []

    def sinal(nome, texto):
        motivos.append({"sinal": nome, "peso": pesos.get(nome, 0), "texto": texto})

    def informar(nome, texto):
        motivos.append({"sinal": nome, "peso": 0, "texto": texto})

    if reposicao:
        return {"score": 0, "nivel": "reposicao", "motivos": [{"sinal": "reposicao", "peso": 0, "texto": reposicao}]}
    if pegadas == 0:
        return {"score": 0, "nivel": "ok", "motivos": [{"sinal": "sem_pegada", "peso": 0, "texto": "não pegou produto"}]}

    if pagamento:
        informar("pagou", f"pagamento aprovado de R$ {pagamento.get('valor') or 0:.2f}")
        quantidade = pagamento.get("qtd_itens")
        if quantidade is not None and pegadas > quantidade + f["tolerancia_itens"]:
            sinal("itens_a_mais", f"pegou {pegadas}x e pagou {quantidade} item(ns)")
        if pagamento.get("metodo") in METODOS_APP:
            informar("pagou_pelo_app", f"pagou pelo celular ({pagamento['metodo']})")
        elif totem_coberto and not foi_totem:
            informar("pagou_fora_do_totem", "não foi visto no totem")
    else:
        sinal("sem_pagamento", f"pegou {pegadas}x e não há pagamento aprovado na janela")
        if foi_totem:
            sinal("totem_sem_pagamento", "esteve no totem e nenhum pagamento foi aprovado")
        elif totem_coberto:
            sinal("nao_foi_ao_totem", "a câmera do totem não o viu pagar")
        if pegadas >= MIN_PEGADAS_VARIAS:
            sinal("varias_pegadas", f"{pegadas} pegadas")
        if saiu_com_produto:
            sinal("saiu_com_produto", "ainda estava com o produto na mão quando sumiu da imagem")
        if produto_s is not None and produto_s < f["produto_firme_s"]:
            sinal("pegada_fraca", f"produto na mão só {produto_s:.1f}s: pode ter devolvido ou ser engano do modelo")
        if objeto_proprio:
            sinal("entrou_com_objeto", "entrou já com algo na mão: o produto pode ser o mesmo objeto")
        if duracao < f["visita_minima_s"]:
            sinal("provavel_fragmento", f"só {duracao:.0f}s de imagem: provável pedaço de rastreio")
        if grupo_pagou:
            sinal("acompanhante_pagou", "entrou junto com alguém que pagou")
        if fragmentos > MAX_FRAGMENTOS:
            sinal("rastreio_fragmentado", f"rastreio partido em {fragmentos} pedaços")

    score = max(0, min(100, sum(m["peso"] for m in motivos)))
    niveis = f["niveis"]
    nivel = "alerta" if score >= niveis["alerta"] else "atencao" if score >= niveis["atencao"] else "ok"
    if not pagamento and nivel == "alerta" and not (totem_coberto and pdv_conhecido):
        nivel = "atencao"
        informar("so_api", "totem fora das câmeras: só a API confirma o pagamento" if pdv_conhecido
                 else "PDV TouchPay desta loja não configurado")
    return {"score": score, "nivel": nivel, "motivos": motivos}


class Fusao:
    def __init__(self, cfg, banco, evidencias=None, notificar=None, triagem=None):
        self.f = cfg["fusao"]
        self.fuso = ZoneInfo(cfg["sistema"]["fuso"])
        self.cfg = cfg
        self.loja_da_camera = {nome: c.get("loja") for nome, c in cfg["cameras"].items()}
        self.cobre_totem = lambda camera: cfg["cameras"].get(camera, {}).get("cobre_totem") is True
        self.banco = banco
        self.evidencias = evidencias
        self.notificar = notificar or (lambda tipo, dados: None)
        self.triagem = triagem
        self.pendentes = []
        self.decididas = deque(maxlen=300)
        self.lock = threading.Lock()
        self._contador = 0
        self._ultima_revisao = 0.0

    def adicionar(self, parte):
        with self.lock:
            loja = self.loja_da_camera.get(parte.camera)
            visita = self._visita_para(parte, loja)
            if visita is None:
                self._contador += 1
                visita = Visita(f"{datetime.fromtimestamp(parte.inicio, self.fuso):%Y%m%d-%H%M%S}-{self._contador}", loja)
                self.pendentes.append(visita)
            visita.partes.append(parte)

    def _visita_para(self, parte, loja):
        janela = self.f["janela_cameras_s"]
        candidatas = [
            v for v in self.pendentes
            if v.loja == loja
            and not (parte.inicio > v.fim + janela or parte.fim < v.inicio - janela)
            and not any(p.camera == parte.camera and min(p.fim, parte.fim) - max(p.inicio, parte.inicio) > 2 for p in v.partes)
        ]
        if not candidatas:
            return None
        pontuadas = [(semelhanca(v.hist, parte.hist), v) for v in candidatas]
        if len(candidatas) == 1:
            similaridade, visita = pontuadas[0]
            return visita if similaridade is None or similaridade >= self.f["aparencia_minima_unica"] else None
        validas = [(s, v) for s, v in pontuadas if s is not None]
        if not validas:
            return None
        similaridade, visita = max(validas, key=lambda x: x[0])
        return visita if similaridade >= self.f["aparencia_minima"] else None

    def tick(self, agora=None):
        agora = agora or time.time()
        with self.lock:
            prontas = [v for v in self.pendentes if agora >= v.fim + self._espera(v.loja)]
            for visita in sorted(prontas, key=lambda v: v.fim):
                self.pendentes.remove(visita)
                self._decidir(visita)
                self.decididas.append(visita)
        if agora - self._ultima_revisao >= INTERVALO_REVISAO_S:
            self._ultima_revisao = agora
            self.revisar_pagamentos_tardios(agora)

    def _espera(self, loja):
        recorte = recorte_sem_compra(self.cfg, loja)
        return max(self.f["aguardar_pagamento_s"], recorte["espera_s"]) if recorte["ativo"] else self.f["aguardar_pagamento_s"]

    def _janela(self, v):
        return v.inicio - self.f["pagamento_antes_s"], v.fim + self._espera(v.loja)

    def inicio_mais_antigo_pendente(self):
        with self.lock:
            return min((v.inicio for v in self.pendentes), default=None)

    def _dono_preferido(self, pagamento, v):
        distancia = abs(pagamento["horario"] - v.referencia_pagamento)
        for outra in self.pendentes:
            inicio, fim = self._janela(outra)
            if (outra is not v and outra.loja == v.loja and inicio <= pagamento["horario"] <= fim and outra.totem
                    and abs(pagamento["horario"] - outra.referencia_pagamento) < distancia and not v.totem):
                return False
        return True

    def _grupo(self, v):
        grupo = []
        for outra in list(self.decididas) + self.pendentes:
            if outra is v or outra.loja != v.loja or abs(outra.inicio - v.inicio) > self.f["grupo_entrada_s"]:
                continue
            sobreposicao = min(outra.fim, v.fim) - max(outra.inicio, v.inicio)
            if sobreposicao >= 0.5 * min(outra.fim - outra.inicio, v.fim - v.inicio):
                grupo.append(outra)
        return grupo

    def _reposicao(self, v):
        regras = self.f.get("reposicao") or {}
        local = datetime.fromtimestamp(v.inicio, self.fuso).strftime("%H:%M")
        for faixa in regras.get("horarios") or []:
            inicio, fim = faixa.split("-")
            if inicio <= local <= fim:
                return f"horário de reposição ({faixa})"
        if not regras.get("usar_movimentacoes_estoque", True):
            return None
        margem = regras.get("margem_movimentacao_s", 300)
        movimentacoes = self.banco.operador_entre(v.inicio - margem, v.fim + margem, pdvs_da_loja(self.cfg, v.loja))
        if not movimentacoes:
            return None
        quem = sorted({m["usuario"] or "operador" for m in movimentacoes})
        return f"{len(movimentacoes)} movimentação(ões) de estoque durante a visita ({', '.join(quem)})"

    def _pagamento_livre(self, pagamento, pegadas):
        if not pagamento["visita_id"]:
            return True
        return pegadas > 0 and self.banco.pegadas_da_visita(pagamento["visita_id"]) == 0

    @staticmethod
    def _da_loja(pagamentos, pdvs):
        return [p for p in pagamentos if p["pdv"] in pdvs]

    def _escolher_pagamento(self, v, pegadas, pdvs):
        inicio, fim = self._janela(v)
        aprovados = [p for p in self._da_loja(self.banco.pagamentos_entre(inicio, fim), pdvs)
                     if p["situacao"] == "aprovado" and self._pagamento_livre(p, pegadas) and self._dono_preferido(p, v)]
        return min(aprovados, key=lambda p: abs(p["horario"] - v.referencia_pagamento)) if aprovados else None

    def _decidir(self, v):
        pegadas = v.pegadas(self.f["pegada_duplicada_s"])
        pdvs = pdvs_da_loja(self.cfg, v.loja)
        pagamento = self._escolher_pagamento(v, pegadas, pdvs)
        grupo = self._grupo(v)
        resultado = avaliar(
            pegadas=pegadas, foi_totem=bool(v.totem), totem_coberto=any(self.cobre_totem(c) for c in v.cameras),
            pdv_conhecido=bool(pdvs), pagamento=pagamento, duracao=v.fim - v.inicio, fragmentos=v.fragmentos,
            grupo_pagou=any(g.resultado and g.resultado.get("pagamento_id") for g in grupo),
            reposicao=self._reposicao(v), f=self.f, produto_s=v.produto_s, saiu_com_produto=v.saiu_com_produto,
            objeto_proprio=v.objeto_proprio)
        resultado.update({
            "id": v.id, "loja": v.loja, "inicio": v.inicio, "fim": v.fim, "cameras": v.cameras, "pegadas": pegadas,
            "foi_totem": bool(v.totem), "pagamento_id": pagamento["id"] if pagamento else None,
            "grupo": [g.id for g in grupo], "partes": [p.resumo() for p in v.partes],
        })
        v.resultado = resultado
        if pagamento:
            if pagamento["visita_id"] and pagamento["visita_id"] != v.id:
                self.banco.liberar_pagamento(pagamento["visita_id"])
            self.banco.associar_pagamento(pagamento["id"], v.id)
        self.banco.salvar_visita(resultado)
        log.info("visita %s | %s | pegou %sx | %s | %s (%s)", v.id, "/".join(v.cameras), pegadas,
                 "pagou" if pagamento else "sem pagamento", resultado["nivel"], resultado["score"])
        self.notificar("visita", {"id": v.id, "loja": v.loja, "nivel": resultado["nivel"]})
        if resultado["nivel"] in NIVEIS_DE_OCORRENCIA:
            self._abrir_ocorrencia(v, resultado)
        elif self._entrou_sem_comprar(v, resultado, pagamento, grupo):
            self._abrir_ocorrencia(v, self._registro_sem_compra(v, resultado), tipo="sem_compra")

    def _entrou_sem_comprar(self, v, resultado, pagamento, grupo):
        return (recorte_sem_compra(self.cfg, v.loja)["ativo"] and not pagamento and resultado["nivel"] != "reposicao"
                and v.fim - v.inicio >= self.f["visita_minima_s"]
                and not any(g.resultado and g.resultado.get("pagamento_id") for g in grupo))

    def _registro_sem_compra(self, v, resultado):
        minutos = round(self._espera(v.loja) / 60)
        motivos = [{"sinal": "entrou_sem_comprar", "peso": 0,
                    "texto": f"entrou e saiu sem compra na TouchPay (esperou {minutos} min depois da saída)"}]
        visao = [f"pegou produto {resultado['pegadas']}x" if resultado["pegadas"] else "não foi visto pegando produto",
                 "passou no totem" if resultado["foi_totem"] else "não passou no totem"]
        motivos.append({"sinal": "visao_computacional", "peso": 0, "texto": "visão computacional: " + ", ".join(visao)})
        return {**resultado, "nivel": "atencao", "score": 0, "motivos": motivos}

    def _abrir_ocorrencia(self, v, resultado, tipo="suspeita"):
        evidencias = [e for p in v.partes for e in p.evidencias]
        vai_para_triagem = bool(tipo == "suspeita" and self.triagem and self.triagem.aceita(resultado))
        ocorrencia_id = self.banco.criar_ocorrencia(resultado, evidencias, "triagem" if vai_para_triagem else "aberta", tipo)
        if ocorrencia_id is None:
            return
        if self.evidencias:
            self.evidencias.pedir_clipes(ocorrencia_id, v, todas_da_loja=tipo == "sem_compra")
        if vai_para_triagem:
            self.notificar("ocorrencia_triagem", {"id": ocorrencia_id, "loja": v.loja, "nivel": resultado["nivel"]})
        else:
            self.notificar("ocorrencia", aviso_de_ocorrencia(ocorrencia_id, resultado, evidencias))

    def _resolver(self, ocorrencia, pagamento_id, motivo, nivel_visita):
        self.banco.resolver_ocorrencia(ocorrencia["visita_id"], pagamento_id, motivo, nivel_visita)
        log.info("ocorrência %s resolvida: %s", ocorrencia["id"], motivo)
        self.notificar("ocorrencia_resolvida", {"id": ocorrencia["id"], "motivo": motivo})

    def revisar_pagamentos_tardios(self, agora):
        regras = self.f.get("reposicao") or {}
        for ocorrencia in self.banco.ocorrencias_abertas_desde(agora - self.f["revisar_tardios_min"] * 60):
            pdvs = pdvs_da_loja(self.cfg, ocorrencia["loja"])
            if regras.get("usar_movimentacoes_estoque", True):
                margem = regras.get("margem_movimentacao_s", 300)
                movimentacoes = self.banco.operador_entre(ocorrencia["inicio"] - margem, ocorrencia["fim"] + margem, pdvs)
                if movimentacoes:
                    quem = ", ".join(sorted({m["usuario"] or "operador" for m in movimentacoes}))
                    self._resolver(ocorrencia, None, f"movimentação de estoque durante a visita ({quem})", "reposicao")
                    continue
            inicio = ocorrencia["inicio"] - self.f["pagamento_antes_s"]
            fim = ocorrencia["fim"] + max(self.f["aguardar_pagamento_s"] * 3, self._espera(ocorrencia["loja"]))
            livres = [p for p in self._da_loja(self.banco.pagamentos_entre(inicio, fim), pdvs)
                      if p["situacao"] == "aprovado" and self._pagamento_livre(p, 1)]
            if livres:
                pagamento = min(livres, key=lambda p: abs(p["horario"] - ocorrencia["fim"]))
                if pagamento["visita_id"]:
                    self.banco.liberar_pagamento(pagamento["visita_id"])
                self._resolver(ocorrencia, pagamento["id"], "pagamento chegou depois da decisão", "ok")
                continue
            pagou = next((g for g in ocorrencia["grupo"] if self.banco.pagamento_da_visita(g)), None)
            if pagou:
                self._resolver(ocorrencia, None, f"entrou junto com a visita {pagou}, que pagou", "ok")

    def estado(self):
        with self.lock:
            return [{"id": v.id, "loja": v.loja, "cameras": v.cameras, "inicio": v.inicio, "fim": v.fim,
                     "pegadas": v.pegadas(self.f["pegada_duplicada_s"]), "foi_totem": bool(v.totem),
                     "decide_em": v.fim + self._espera(v.loja)} for v in self.pendentes]
