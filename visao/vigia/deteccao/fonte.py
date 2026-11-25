import subprocess
import threading
import time
from pathlib import Path

import numpy as np

SEM_SINAL_S = 5
TIMEOUT_REDE_US = "10000000"
ESPERA_RECONEXAO_S = 2
ESPERA_SEM_STREAM_S = 3


class Fonte:
    def __init__(self, nome, url, fps, largura):
        self.nome = nome
        self.url = url
        self.fps = fps
        self.largura = largura
        self.arquivo = Path(url).exists()
        self.lock = threading.Lock()
        self.frame = None
        self.t = 0.0
        self.seq = 0
        self.erro = ""
        self.terminou = False
        self._processo = None
        self._parar = threading.Event()

    def iniciar(self):
        threading.Thread(target=self._rodar, name=f"fonte-{self.nome}", daemon=True).start()
        return self

    @property
    def online(self):
        return time.time() - self.t < SEM_SINAL_S

    def ultimo(self):
        with self.lock:
            return self.seq, self.frame, self.t

    def _opcoes_de_rede(self):
        if self.url.startswith("rtsp://"):
            return ["-rtsp_transport", "tcp", "-timeout", TIMEOUT_REDE_US]
        return [] if self.arquivo else ["-rw_timeout", TIMEOUT_REDE_US]

    def _dimensoes(self):
        comando = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                   "-of", "csv=p=0:s=x", *self._opcoes_de_rede(), self.url]
        saida = subprocess.run(comando, capture_output=True, text=True, timeout=30)
        largura, altura = (int(v) for v in saida.stdout.strip().splitlines()[0].split("x")[:2])
        return largura, altura

    def _comando(self, largura, altura):
        entrada = ["-re"] if self.arquivo else ["-fflags", "nobuffer", "-flags", "low_delay", *self._opcoes_de_rede()]
        return ["ffmpeg", "-nostdin", "-loglevel", "error", "-threads", "1", *entrada, "-i", self.url,
                "-an", "-sn", "-dn", "-vf", f"fps={self.fps},scale={largura}:{altura}",
                "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"]

    def _rodar(self):
        while not self._parar.is_set():
            try:
                largura_original, altura_original = self._dimensoes()
            except Exception:
                self.erro = "sem sinal"
                time.sleep(ESPERA_SEM_STREAM_S)
                continue
            largura = min(self.largura, largura_original) // 2 * 2
            altura = round(altura_original * largura / largura_original / 2) * 2
            self._ler(largura, altura)
            if self.arquivo:
                self.terminou = True
                return
            self.erro = "sinal caiu, reconectando"
            time.sleep(ESPERA_RECONEXAO_S)

    def _ler(self, largura, altura):
        tamanho = largura * altura * 3
        self._processo = subprocess.Popen(self._comando(largura, altura), stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, bufsize=tamanho * 2)
        self.erro = ""
        try:
            while not self._parar.is_set():
                dados = self._processo.stdout.read(tamanho)
                if len(dados) < tamanho:
                    return
                frame = np.frombuffer(dados, np.uint8).reshape(altura, largura, 3)
                with self.lock:
                    self.frame, self.t = frame, time.time()
                    self.seq += 1
        finally:
            self._processo.kill()
            self._processo.wait()

    def parar(self):
        self._parar.set()
        if self._processo is not None:
            self._processo.kill()
