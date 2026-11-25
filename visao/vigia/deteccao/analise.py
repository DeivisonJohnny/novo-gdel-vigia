import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from .marcacao import origem_da_marcacao

MAX_FOTOS_PEGADA = 3
MAX_OBJETOS_PROPRIOS = 3
MAX_EVENTOS = 40
SAIU_COM_PRODUTO_S = 3.0
PRODUTO_SUMIU_DA_TELA_S = 1.0
INTERVALO_AMOSTRA_ROUPA_S = 1.0
TOTEM_REAPRENDER_A_CADA = 60
TOTEM_IOU_CONSENSO = 0.3
TOTEM_CONSENSO_MINIMO = 0.6
TOTEM_SOBREPOSICAO_MINIMA = 0.15
DONO_FOLGA_X = 0.2
DONO_FOLGA_Y = 0.1
IOU_CELULAR = 0.3
QUALIDADE_FOTO = 80
QUALIDADE_AO_VIVO = 70
COR_PESSOA = (0, 200, 255)
COR_PRODUTO = (255, 0, 255)


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    intersecao = ix * iy
    uniao = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersecao
    return intersecao / uniao if uniao > 0 else 0.0


def _histograma(frame, x1, y1, x2, y2, bins, area_minima):
    altura, largura = frame.shape[:2]
    x1, y1 = int(max(x1, 0)), int(max(y1, 0))
    x2, y2 = int(min(x2, largura)), int(min(y2, altura))
    if (x2 - x1) * (y2 - y1) < area_minima:
        return None
    hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, bins, [0, 180, 0, 256]).flatten()
    return hist / max(float(hist.sum()), 1e-6)


def histograma_roupa(frame, caixa):
    x1, y1, x2, y2 = caixa
    w, h = x2 - x1, y2 - y1
    return _histograma(frame, x1 + 0.2 * w, y1 + 0.15 * h, x2 - 0.2 * w, y1 + 0.55 * h, [16, 8], 300)


def histograma_objeto(frame, caixa):
    return _histograma(frame, *caixa, [12, 6], 64)


def semelhanca(a, b):
    if a is None or b is None:
        return None
    return 1.0 - float(cv2.compareHist(a.astype(np.float32), b.astype(np.float32), cv2.HISTCMP_BHATTACHARYYA))


@dataclass(eq=False)
class PessoaCamera:
    camera: str
    id: str
    inicio: float
    fim: float
    ancora: tuple = (0, 0)
    caixa: tuple = (0, 0, 0, 0)
    ids_rastreador: set = field(default_factory=set)
    deteccoes: int = 0
    pegadas: list = field(default_factory=list)
    totem: list = field(default_factory=list)
    evidencias: list = field(default_factory=list)
    em_contato: bool = False
    totem_s: float = 0.0
    totem_desde: float = None
    no_totem: bool = False
    produto_vistos: deque = field(default_factory=deque)
    produto_caixa: tuple = None
    sem_produto_s: float = 0.0
    mao_vazia_s: float = 0.0
    vazia_antes_s: float = 0.0
    trecho_conta: bool = None
    objetos_proprios: list = field(default_factory=list)
    produto_s: float = None
    ultimo_produto: float = None
    _soma_hist: np.ndarray = None
    _n_hist: int = 0
    _ultima_amostra: float = 0.0
    _melhor: tuple = None

    @property
    def hist(self):
        return None if self._soma_hist is None else self._soma_hist / self._n_hist

    @property
    def duracao(self):
        return self.fim - self.inicio

    @property
    def saiu_com_produto(self):
        return self.ultimo_produto is not None and self.fim - self.ultimo_produto <= SAIU_COM_PRODUTO_S

    @property
    def numero(self):
        return self.id.rsplit("-", 1)[-1]

    def somar_hist(self, hist):
        self._soma_hist = hist.copy() if self._soma_hist is None else self._soma_hist + hist
        self._n_hist += 1

    def resumo(self):
        return {
            "camera": self.camera, "id": self.id, "inicio": self.inicio, "fim": self.fim,
            "pegadas": self.pegadas, "totem": self.totem, "ids_rastreador": len(self.ids_rastreador),
            "deteccoes": self.deteccoes, "evidencias": self.evidencias,
            "produto_s": None if self.produto_s is None else round(self.produto_s, 1),
            "saiu_com_produto": self.saiu_com_produto, "objeto_proprio": bool(self.objetos_proprios),
        }


class CameraAnalise:
    def __init__(self, camera, p, pasta_evidencias, pasta_totem, ao_finalizar, ao_evento=None, coleta=None, maquininhas=None):
        from ultralytics.trackers.byte_tracker import BYTETracker

        from .modelo import FiltroMovimento

        self.nome = camera["nome"]
        self.descricao = camera.get("descricao", self.nome)
        self.loja = camera.get("loja")
        self.camera = camera
        self.p = p
        self.tracker = BYTETracker(SimpleNamespace(
            track_high_thresh=p["conf_pessoa"], track_low_thresh=p["conf_minima"],
            new_track_thresh=p["conf_pessoa"], track_buffer=max(int(p["fps_analise"] * 2), 10),
            match_thresh=0.8, fuse_score=True))
        self.filtro = FiltroMovimento(p)
        self.ativas = {}
        self.perdidas = []
        self.ao_finalizar = ao_finalizar
        self.ao_evento = ao_evento
        self.coleta = coleta
        self.raiz_evidencias = Path(pasta_evidencias)
        self.pasta = self.raiz_evidencias / self.nome
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.seq_processado = -1
        self.uso_ia = 0.0
        self.fps = 0.0
        self.tamanho = None
        self.diagonal = 1.0
        self._ultimo_t = 0.0
        self._contador = 0
        self._momento = False
        self.lock = threading.Lock()
        self.ultimo_frame = None
        self.deteccao = None
        self.eventos = deque(maxlen=MAX_EVENTOS)
        self.totem_vistos = deque(maxlen=300)
        self._totem_novos = 0
        self.arquivo_totem = Path(pasta_totem) / f"{self.nome}.json"
        self.totem_norm = self._carregar_totem()
        self.maquininhas = None
        self.marcar_maquininhas(maquininhas)

    def _carregar_totem(self):
        try:
            return json.loads(self.arquivo_totem.read_text())["caixa"]
        except (OSError, ValueError, KeyError):
            return None

    def marcar_maquininhas(self, caixas):
        self.maquininhas = None if caixas is None else [[float(v) for v in caixa] for caixa in caixas]
        if self.sem_maquininha:
            self._esquecer_totem_aprendido()

    def _esquecer_totem_aprendido(self):
        self.totem_norm = None
        self.totem_vistos.clear()
        self._totem_novos = 0
        self.arquivo_totem.unlink(missing_ok=True)

    @property
    def marcada_pelo_admin(self):
        return self.maquininhas is not None

    @property
    def sem_maquininha(self):
        return self.maquininhas == []

    @property
    def totens(self):
        if self.marcada_pelo_admin:
            return self.maquininhas
        return [self.totem_norm] if self.totem_norm else []

    @property
    def cobre_totem(self):
        if self.marcada_pelo_admin:
            return bool(self.maquininhas)
        forcado = self.camera.get("cobre_totem")
        if isinstance(forcado, bool):
            return forcado
        return self.totem_norm is not None

    @property
    def origem_totem(self):
        if self.marcada_pelo_admin:
            return origem_da_marcacao(self.maquininhas, sem_marcacao=None)
        if isinstance(self.camera.get("cobre_totem"), bool):
            return "configurado"
        return "aprendido" if self.totem_norm else "procurando"

    def _caixas_totem(self):
        if self.tamanho is None:
            return []
        largura, altura = self.tamanho
        return [(x1 * largura, y1 * altura, x2 * largura, y2 * altura) for x1, y1, x2, y2 in self.totens]

    def _observar_totens(self, caixas):
        if not self.marcada_pelo_admin:
            self._aprender_totem(caixas)

    def _aprender_totem(self, caixas):
        if not caixas:
            return
        self.totem_vistos.extend(tuple(map(float, c)) for c in caixas)
        self._totem_novos += len(caixas)
        ja_aprendido = self.totem_norm is not None
        if len(self.totem_vistos) < self.p["totem_min_deteccoes"] or (ja_aprendido and self._totem_novos < TOTEM_REAPRENDER_A_CADA):
            return
        self._totem_novos = 0
        mediana = np.median(np.array(self.totem_vistos), axis=0)
        consenso = float(np.mean([iou(c, mediana) >= TOTEM_IOU_CONSENSO for c in self.totem_vistos]))
        if consenso < TOTEM_CONSENSO_MINIMO:
            return
        largura, altura = self.tamanho
        self.totem_norm = [round(float(v), 4) for v in (mediana[0] / largura, mediana[1] / altura,
                                                        mediana[2] / largura, mediana[3] / altura)]
        self.arquivo_totem.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo_totem.write_text(json.dumps({"caixa": self.totem_norm, "deteccoes": len(self.totem_vistos),
                                                  "consenso": round(consenso, 2), "em": time.time()}))
        if not ja_aprendido:
            self._registrar_evento(time.time(), None, "totem_aprendido", "câmera passou a ver o totem")

    def _perto_do_totem(self, caixa):
        return any(self._perto_da_area(caixa, totem) for totem in self._caixas_totem())

    @staticmethod
    def _perto_da_area(caixa, totem):
        tx1, ty1, tx2, ty2 = totem
        w, h = tx2 - tx1, ty2 - ty1
        ex1, ey1, ex2, ey2 = tx1 - w, ty1 - h, tx2 + w, ty2 + h
        ix = max(0.0, min(caixa[2], ex2) - max(caixa[0], ex1))
        iy = max(0.0, min(caixa[3], ey2) - max(caixa[1], ey1))
        return ix * iy >= TOTEM_SOBREPOSICAO_MINIMA * (ex2 - ex1) * (ey2 - ey1)

    @staticmethod
    def _donos_dos_produtos(produtos, caixas):
        donos = {}
        for produto in produtos:
            cx, cy = (produto[0] + produto[2]) / 2, (produto[1] + produto[3]) / 2
            candidatos = []
            for indice, (x1, y1, x2, y2) in enumerate(caixas):
                mx, my = DONO_FOLGA_X * (x2 - x1), DONO_FOLGA_Y * (y2 - y1)
                if x1 - mx <= cx <= x2 + mx and y1 - my <= cy <= y2 + my:
                    candidatos.append((np.hypot(cx - (x1 + x2) / 2, cy - (y1 + y2) / 2), indice))
            if candidatos:
                donos.setdefault(min(candidatos)[1], produto)
        return donos

    def _registrar_evento(self, t, pessoa, tipo, texto):
        evento = {"t": t, "camera": self.nome, "loja": self.loja, "pessoa": pessoa.numero if pessoa else None,
                  "tipo": tipo, "texto": texto}
        self.eventos.appendleft(evento)
        if self.ao_evento:
            self.ao_evento(evento)

    def _separar_deteccoes(self, deteccoes, modelo):
        classes, confiancas = deteccoes.cls.astype(int), deteccoes.conf
        produtos = [caixa for caixa, conf, classe in zip(deteccoes.xyxy, confiancas, classes)
                    if classe == modelo.ids["produto"] and conf >= self.p["conf_produto"]]
        if "celular" in modelo.ids:
            celulares = [caixa for caixa, classe in zip(deteccoes.xyxy, classes) if classe == modelo.ids["celular"]]
            produtos = [caixa for caixa in produtos if all(iou(caixa, c) < IOU_CELULAR for c in celulares)]
        totens = [caixa for caixa, conf, classe in zip(deteccoes.xyxy, confiancas, classes)
                  if classe == modelo.ids["totem"] and conf >= self.p["conf_totem"]]
        return deteccoes[classes == modelo.ids["cliente"]], produtos, totens

    def processar(self, frame, t, modelo):
        if self.tamanho is None:
            altura, largura = frame.shape[:2]
            self.tamanho = (largura, altura)
            self.diagonal = float(np.hypot(largura, altura))
        if self._ultimo_t:
            self.fps += 0.1 * (1 / max(t - self._ultimo_t, 1e-3) - self.fps)
        self._ultimo_t = t
        with self.lock:
            self.ultimo_frame = frame

        analisar = self.filtro.deve_analisar(frame, t, bool(self.ativas))
        self.uso_ia += 0.05 * (analisar - self.uso_ia)
        if not analisar:
            self._verificar_perdidas(set(self.ativas), t)
            self._publicar(t, list(self.ativas.values()), analisou=False)
            return

        clientes, produtos, totens = self._separar_deteccoes(modelo.inferir(frame).boxes.cpu().numpy(), modelo)
        self._observar_totens(totens)
        trilhas = self.tracker.update(clientes, frame)
        donos = self._donos_dos_produtos(produtos, [linha[:4] for linha in trilhas])
        vistas, presentes = set(), []
        for indice, linha in enumerate(trilhas):
            x1, y1, x2, y2, tid = linha[:5]
            pessoa = self._pessoa(int(tid), ((x1 + x2) / 2, y2), t)
            vistas.add(int(tid))
            self._atualizar(pessoa, frame, t, (x1, y1, x2, y2), donos.get(indice))
            presentes.append(pessoa)

        if self.coleta is not None:
            self.coleta.observar(self.nome, frame, t, [p.caixa for p in presentes], importante=self._momento)
        self._momento = False
        self._verificar_perdidas(vistas, t)
        self._publicar(t, presentes, analisou=True)

    def _publicar(self, t, pessoas, analisou):
        if self.tamanho is None:
            return
        largura, altura = self.tamanho

        def normalizar(x1, y1, x2, y2):
            return [round(x1 / largura, 4), round(y1 / altura, 4), round(x2 / largura, 4), round(y2 / altura, 4)]

        self.deteccao = {
            "t": t, "analisou": analisou, "fps": round(self.fps, 1), "uso_ia": round(self.uso_ia, 2),
            "totens": self.totens, "origem_totem": self.origem_totem,
            "pessoas": [{
                "id": p.numero, "caixa": normalizar(*p.caixa), "pegadas": len(p.pegadas), "totem": bool(p.totem),
                "produto": normalizar(*p.produto_caixa) if p.produto_caixa else None,
                "no_totem_agora": p.no_totem, "segundos": round(t - p.inicio),
            } for p in pessoas],
        }

    def _pessoa(self, tid, ancora, t):
        pessoa = self.ativas.get(tid)
        if pessoa is not None:
            return pessoa
        pessoa = next((p for p in self.perdidas if tid in p.ids_rastreador), None) or self._perdida_proxima(ancora)
        if pessoa is not None:
            self.perdidas.remove(pessoa)
        else:
            self._contador += 1
            pessoa = PessoaCamera(self.nome, f"{self.nome}-{int(t)}-{self._contador}", t, t)
            self._registrar_evento(t, pessoa, "entrou", "apareceu na imagem")
        pessoa.ids_rastreador.add(tid)
        self.ativas[tid] = pessoa
        return pessoa

    def _perdida_proxima(self, ancora):
        if not self.perdidas:
            return None
        distancia = lambda p: np.hypot(p.ancora[0] - ancora[0], p.ancora[1] - ancora[1])
        mais_perto = min(self.perdidas, key=distancia)
        return mais_perto if distancia(mais_perto) <= self.p["herdar_max_dist"] * self.diagonal else None

    def _atualizar(self, pessoa, frame, t, caixa, produto):
        dt = min(t - pessoa.fim, 0.5)
        pessoa.fim = t
        pessoa.deteccoes += 1
        pessoa.caixa = tuple(int(v) for v in caixa)
        pessoa.ancora = (int((caixa[0] + caixa[2]) / 2), int(caixa[3]))
        self._produto_na_mao(pessoa, frame, t, dt, produto)
        self._passagem_no_totem(pessoa, frame, t, dt, caixa)
        if t - pessoa._ultima_amostra >= INTERVALO_AMOSTRA_ROUPA_S:
            hist = histograma_roupa(frame, caixa)
            if hist is not None:
                pessoa.somar_hist(hist)
                pessoa._ultima_amostra = t
        area = (caixa[2] - caixa[0]) * (caixa[3] - caixa[1])
        if pessoa._melhor is None or area > pessoa._melhor[0]:
            pessoa._melhor = (area, frame, pessoa.caixa)

    def _passagem_no_totem(self, pessoa, frame, t, dt, caixa):
        if not self._perto_do_totem(caixa):
            pessoa.totem_s = 0.0
            pessoa.totem_desde = None
            pessoa.no_totem = False
            return
        if pessoa.totem_desde is None:
            pessoa.totem_desde = t
        pessoa.totem_s += dt
        if pessoa.no_totem:
            pessoa.totem[-1][1] = t
        elif pessoa.totem_s >= self.p["pagar_min_s"]:
            pessoa.no_totem = True
            pessoa.totem.append([pessoa.totem_desde, t])
            self._registrar_evento(t, pessoa, "totem", "foi ao totem")
            self._momento = True
            pessoa.evidencias.append(self._foto(frame, pessoa, "totem"))

    def _sem_produto(self, pessoa, dt):
        pessoa.sem_produto_s += dt
        pessoa.mao_vazia_s += dt
        if pessoa.sem_produto_s >= PRODUTO_SUMIU_DA_TELA_S:
            pessoa.produto_caixa = None
        if pessoa.sem_produto_s >= self.p["produto_intervalo_s"]:
            pessoa.em_contato = False
            pessoa.trecho_conta = None
            pessoa.produto_vistos.clear()

    def _motivo_para_ignorar(self, pessoa, cor):
        if pessoa.vazia_antes_s < self.p["mao_vazia_antes_s"]:
            return "já estava com o objeto na mão ao aparecer"
        if cor is not None and any(semelhanca(cor, o) >= self.p["mesmo_objeto"] for o in pessoa.objetos_proprios):
            return "é o mesmo objeto que trouxe (mesma cor)"
        return None

    def _produto_na_mao(self, pessoa, frame, t, dt, produto):
        if produto is None:
            self._sem_produto(pessoa, dt)
            return
        if pessoa.sem_produto_s >= PRODUTO_SUMIU_DA_TELA_S or not pessoa.produto_vistos:
            pessoa.vazia_antes_s = pessoa.mao_vazia_s
        pessoa.sem_produto_s = 0.0
        pessoa.produto_caixa = tuple(int(v) for v in produto)
        pessoa.produto_vistos.append(t)
        if pessoa.trecho_conta:
            pessoa.produto_s += dt
            pessoa.ultimo_produto = t
        while pessoa.produto_vistos and t - pessoa.produto_vistos[0] > self.p["produto_janela_s"]:
            pessoa.produto_vistos.popleft()
        if pessoa.em_contato:
            pessoa.mao_vazia_s = 0.0
            return
        if len(pessoa.produto_vistos) < self.p["produto_min_deteccoes"]:
            return
        pessoa.em_contato = True
        pessoa.mao_vazia_s = 0.0
        cor = histograma_objeto(frame, produto)
        motivo = self._motivo_para_ignorar(pessoa, cor)
        if motivo:
            pessoa.trecho_conta = False
            if cor is not None and len(pessoa.objetos_proprios) < MAX_OBJETOS_PROPRIOS:
                pessoa.objetos_proprios.append(cor)
            self._registrar_evento(t, pessoa, "objeto", f"objeto na mão não conta: {motivo}")
            return
        pessoa.trecho_conta = True
        pessoa.produto_s = pessoa.produto_s or 0.0
        pessoa.ultimo_produto = t
        pessoa.pegadas.append(t)
        self._registrar_evento(t, pessoa, "pegou", f"produto na mão ({len(pessoa.pegadas)}º item)")
        self._momento = True
        if len(pessoa.pegadas) <= MAX_FOTOS_PEGADA:
            pessoa.evidencias.append(self._foto(frame, pessoa, f"pegou{len(pessoa.pegadas)}"))

    def inicio_mais_antigo_em_andamento(self):
        return min((p.inicio for p in [*self.ativas.values(), *self.perdidas]), default=None)

    def _verificar_perdidas(self, vistas, t):
        for tid in [tid for tid in self.ativas if tid not in vistas]:
            pessoa = self.ativas.pop(tid)
            if pessoa not in self.perdidas and pessoa not in self.ativas.values():
                self.perdidas.append(pessoa)
        restantes = []
        for pessoa in self.perdidas:
            if t - pessoa.fim <= self.p["esquecer_s"]:
                restantes.append(pessoa)
                continue
            self._finalizar(pessoa, t)
        self.perdidas = restantes

    def _finalizar(self, pessoa, t):
        if pessoa.duracao >= self.p["min_visivel_s"] and pessoa.deteccoes >= self.p["min_deteccoes"]:
            if pessoa._melhor is not None:
                _, frame, caixa = pessoa._melhor
                pessoa.evidencias.insert(0, self._foto(frame, pessoa, "pessoa", caixa))
            self._registrar_evento(t, pessoa, "saiu", f"saiu da imagem · pegou {len(pessoa.pegadas)}x · "
                                                      f"totem: {'sim' if pessoa.totem else 'não'}")
            self.ao_finalizar(pessoa)
        pessoa._melhor = None

    def finalizar_todas(self, t):
        self._verificar_perdidas(set(), t)
        for pessoa in self.perdidas:
            self._finalizar(pessoa, t)
        self.perdidas = []

    def _foto(self, frame, pessoa, rotulo, caixa=None):
        x1, y1, x2, y2 = caixa or pessoa.caixa
        imagem = frame.copy()
        cv2.rectangle(imagem, (x1, y1), (x2, y2), COR_PESSOA, 2)
        if pessoa.produto_caixa:
            px1, py1, px2, py2 = pessoa.produto_caixa
            cv2.rectangle(imagem, (px1, py1), (px2, py2), COR_PRODUTO, 2)
            cv2.putText(imagem, "produto", (px1, max(py1 - 4, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, COR_PRODUTO, 1, cv2.LINE_AA)
        caminho = self.pasta / f"{pessoa.id}_{rotulo}.jpg"
        cv2.imwrite(str(caminho), imagem, [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_FOTO])
        return str(caminho.relative_to(self.raiz_evidencias))

    def jpeg_atual(self):
        with self.lock:
            frame = self.ultimo_frame
        if frame is None:
            return None
        return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_AO_VIVO])[1].tobytes()

    def status(self, fonte):
        online = fonte.online if fonte else False
        return {
            "nome": self.nome, "descricao": self.descricao, "loja": self.loja, "online": online,
            "erro": fonte.erro if fonte else "", "fps": round(self.fps, 1) if online else 0,
            "uso_ia": round(self.uso_ia, 2), "pessoas": len(self.ativas), "cobre_totem": self.cobre_totem,
            "origem_totem": self.origem_totem, "totens": self.totens, "caminho": self.camera["caminho"],
            "eventos": list(self.eventos)[:12],
        }
