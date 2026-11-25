import time
from pathlib import Path

import cv2
import numpy as np

PAPEIS_OBRIGATORIOS = ("cliente", "produto", "totem")
TAMANHO_FILTRO = (160, 120)
APRENDIZADO_FUNDO = 0.05


class ModeloSemClasses(SystemExit):
    pass


class Modelo:
    def __init__(self, p, caminho):
        import torch
        import ultralytics.utils.torch_utils as torch_utils
        from ultralytics import YOLO

        threads = int(p["threads"])
        torch_utils.NUM_THREADS = threads
        torch.set_num_threads(threads)
        self.caminho = Path(caminho)
        self.yolo = YOLO(str(self.caminho), task="detect")
        nomes = {nome: indice for indice, nome in self.yolo.names.items()}
        faltando = [p["classes"][papel] for papel in PAPEIS_OBRIGATORIOS if p["classes"].get(papel) not in nomes]
        if faltando:
            raise ModeloSemClasses(f"{self.caminho.name} não tem as classes {faltando} (tem {list(nomes)}): ajuste visao.classes")
        self.ids = {papel: nomes[nome] for papel, nome in p["classes"].items() if nome in nomes}
        self.classes = list(self.yolo.names.values())
        self.imgsz = int(p["imgsz"])
        self.conf = float(p["conf_minima"])
        self.tempo_ms = 0.0
        self.inferir(np.zeros((480, 640, 3), np.uint8))
        torch.set_num_threads(threads)

    def inferir(self, frame):
        inicio = time.perf_counter()
        resultado = self.yolo.predict(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        ms = (time.perf_counter() - inicio) * 1000
        self.tempo_ms = ms if not self.tempo_ms else self.tempo_ms + 0.1 * (ms - self.tempo_ms)
        return resultado

    def status(self):
        return {"arquivo": self.caminho.name, "classes": self.classes, "inferencia_ms": round(self.tempo_ms, 1)}


class FiltroMovimento:
    def __init__(self, p):
        self.p = p
        self.fundo = None
        self.ultimo_movimento_t = 0.0
        self.ultima_analise_t = 0.0

    def deve_analisar(self, frame, t, tem_pessoas):
        cinza = cv2.cvtColor(cv2.resize(frame, TAMANHO_FILTRO, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        atual = cv2.GaussianBlur(cinza, (5, 5), 0).astype(np.float32)
        if self.fundo is None:
            self.fundo = atual
        area = float((cv2.absdiff(atual, self.fundo) > self.p["movimento_limiar"]).mean())
        cv2.accumulateWeighted(atual, self.fundo, APRENDIZADO_FUNDO)
        if area >= self.p["movimento_area"]:
            self.ultimo_movimento_t = t
        analisar = (tem_pessoas or t - self.ultimo_movimento_t <= self.p["ia_manter_s"]
                    or t - self.ultima_analise_t >= self.p["ia_intervalo_s"])
        if analisar:
            self.ultima_analise_t = t
        return analisar
