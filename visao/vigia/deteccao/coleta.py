import queue
import shutil
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ESPERA_MOMENTO_IMPORTANTE_S = 1.0
VERIFICAR_DISCO_A_CADA_S = 60


class Coleta:
    def __init__(self, c, pasta):
        self.c = c or {}
        self.ativa = bool(self.c.get("ativa"))
        self.pasta = Path(pasta)
        self.fila = queue.Queue(maxsize=30)
        self.por_camera = {}
        self.salvas = 0
        self.sem_disco = 0
        self._disco_ok = True
        self._disco_checado = 0.0
        if self.ativa:
            self.pasta.mkdir(parents=True, exist_ok=True)
            threading.Thread(target=self._gravar, name="coleta", daemon=True).start()

    def _estado(self, camera):
        if camera not in self.por_camera:
            hoje = datetime.now().strftime("%Y%m%d")
            self.por_camera[camera] = {"ultima": 0.0, "assinaturas": deque(), "dia": hoje,
                                       "hoje": len(list(self.pasta.glob(f"{camera}_{hoje}_*.jpg")))}
        return self.por_camera[camera]

    def _tem_disco(self, t):
        if t - self._disco_checado >= VERIFICAR_DISCO_A_CADA_S:
            self._disco_checado = t
            livre_gb = shutil.disk_usage(self.pasta).free / 1e9
            self._disco_ok = livre_gb >= float(self.c.get("espaco_minimo_gb", 5))
        return self._disco_ok

    @staticmethod
    def _assinaturas(caixas, largura, altura):
        return [np.array([(x1 + x2) / 2 / largura, (y1 + y2) / 2 / altura, (x2 - x1) / largura, (y2 - y1) / altura])
                for x1, y1, x2, y2 in caixas]

    def observar(self, camera, frame, t, caixas, importante=False):
        if not self.ativa or not len(caixas):
            return
        estado = self._estado(camera)
        dia = datetime.fromtimestamp(t).strftime("%Y%m%d")
        if dia != estado["dia"]:
            estado["dia"], estado["hoje"] = dia, 0
        if estado["hoje"] >= int(self.c.get("max_por_dia", 1500)):
            return
        espera = ESPERA_MOMENTO_IMPORTANTE_S if importante else float(self.c.get("intervalo_s", 4))
        if t - estado["ultima"] < espera:
            return

        altura, largura = frame.shape[:2]
        atuais = self._assinaturas(caixas, largura, altura)
        memoria = float(self.c.get("memoria_s", 60))
        while estado["assinaturas"] and t - estado["assinaturas"][0][0] > memoria:
            estado["assinaturas"].popleft()
        limite = float(self.c.get("diversidade", 0.05))
        novas = [a for a in atuais if all(np.abs(a - s).max() > limite for _, s in estado["assinaturas"])]
        if not novas and not importante:
            return
        if not self._tem_disco(t):
            self.sem_disco += 1
            return

        estado["ultima"] = t
        estado["hoje"] += 1
        estado["assinaturas"].extend((t, a) for a in atuais)
        nome = f"{camera}_{datetime.fromtimestamp(t):%Y%m%d_%H%M%S}_{int(t * 1000) % 1000:03d}.jpg"
        try:
            self.fila.put_nowait((self.pasta / nome, frame.copy()))
        except queue.Full:
            pass

    def _gravar(self):
        qualidade = int(self.c.get("qualidade_jpeg", 95))
        while True:
            caminho, frame = self.fila.get()
            if cv2.imwrite(str(caminho), frame, [cv2.IMWRITE_JPEG_QUALITY, qualidade]):
                self.salvas += 1

    def status(self):
        return {"ativa": self.ativa, "pasta": str(self.pasta), "salvas_agora": self.salvas,
                "hoje": {camera: e["hoje"] for camera, e in self.por_camera.items()}, "sem_disco": self.sem_disco}
