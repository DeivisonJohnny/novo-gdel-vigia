import logging
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import requests

log = logging.getLogger(__name__)

MARGEM_S = 8
MAX_DURACAO_S = 600
TENTATIVAS = 4
ESPERA_ENTRE_TENTATIVAS_S = 60
TRECHO_MINIMO_S = 0.5
BLOCO_DOWNLOAD = 256 * 1024
RECUPERAR_ULTIMAS_S = 48 * 3600


def iso_utc(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class Evidencias:
    def __init__(self, cfg, banco, pasta, notificar=None):
        self.roteador = cfg["roteador"]
        self.cameras = cfg["cameras"]
        self.banco = banco
        self.raiz = Path(pasta)
        self.pasta = self.raiz / "clipes"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.notificar = notificar or (lambda tipo, dados: None)
        self.fila = []
        self.lock = threading.Lock()
        self.ativo = bool(self.roteador.get("playback"))

    def iniciar(self):
        if self.ativo:
            self.recuperar_pendentes(time.time())
            threading.Thread(target=self._rodar, name="clipes", daemon=True).start()
        return self

    def recuperar_pendentes(self, agora):
        pendentes = self.banco.ocorrencias_sem_clipe(agora - RECUPERAR_ULTIMAS_S)
        for ocorrencia in pendentes:
            visita = SimpleNamespace(inicio=ocorrencia["inicio"], fim=ocorrencia["fim"], cameras=ocorrencia["cameras"],
                                     loja=ocorrencia["loja"])
            self.pedir_clipes(ocorrencia["id"], visita, todas_da_loja=ocorrencia.get("tipo") == "sem_compra")
        if pendentes:
            log.info("buscando o vídeo de %s ocorrência(s) que ficaram sem clipe", len(pendentes))

    def cameras_da_loja(self, loja):
        return [nome for nome, camera in self.cameras.items() if camera.get("loja") == loja]

    def pedir_clipes(self, ocorrencia_id, visita, todas_da_loja=False):
        if not self.ativo:
            return
        cameras = sorted({*visita.cameras, *self.cameras_da_loja(visita.loja)}) if todas_da_loja else visita.cameras
        inicio = visita.inicio - MARGEM_S
        duracao = min(visita.fim - visita.inicio + 2 * MARGEM_S, MAX_DURACAO_S)
        with self.lock:
            self.fila.extend({"ocorrencia": ocorrencia_id, "camera": camera, "inicio": inicio, "duracao": duracao,
                              "tentativa": 0, "quando": time.time()} for camera in cameras if camera in self.cameras)

    def _rodar(self):
        while True:
            time.sleep(5)
            with self.lock:
                prontos = [job for job in self.fila if job["quando"] <= time.time()]
            for job in prontos:
                baixou = self._baixar(job)
                with self.lock:
                    job["tentativa"] += 1
                    if baixou or job["tentativa"] >= TENTATIVAS:
                        self.fila.remove(job)
                    else:
                        job["quando"] = time.time() + ESPERA_ENTRE_TENTATIVAS_S

    def _autenticacao(self):
        return (self.roteador["usuario"], self.roteador.get("senha", "")) if self.roteador.get("usuario") else None

    def _trechos_gravados(self, caminho, inicio, fim):
        base = self.roteador["playback"].rstrip("/")
        resposta = requests.get(f"{base}/list", auth=self._autenticacao(), timeout=30,
                                params={"path": caminho, "start": iso_utc(inicio), "end": iso_utc(fim)})
        if resposta.status_code != 200:
            return []
        trechos = []
        for segmento in resposta.json():
            comeco = datetime.fromisoformat(segmento["start"].replace("Z", "+00:00")).timestamp()
            trecho_inicio, trecho_fim = max(comeco, inicio), min(comeco + float(segmento["duration"]), fim)
            if trecho_fim - trecho_inicio >= TRECHO_MINIMO_S:
                trechos.append((trecho_inicio, trecho_fim - trecho_inicio))
        return trechos

    def _baixar_trecho(self, caminho, inicio, duracao, destino):
        base = self.roteador["playback"].rstrip("/")
        parametros = {"path": caminho, "start": iso_utc(inicio), "duration": f"{duracao:.3f}", "format": "mp4"}
        try:
            with requests.get(f"{base}/get", auth=self._autenticacao(), timeout=120, stream=True, params=parametros) as r:
                if r.status_code != 200:
                    return False
                with open(destino, "wb") as arquivo:
                    for bloco in r.iter_content(BLOCO_DOWNLOAD):
                        arquivo.write(bloco)
            return True
        except requests.RequestException:
            return False

    @staticmethod
    def _juntar(partes, destino, pasta_temporaria):
        if len(partes) == 1:
            shutil.move(partes[0], destino)
            return True
        lista = Path(pasta_temporaria) / "lista.txt"
        lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
        juntar = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                                 "-i", str(lista), "-c", "copy", "-movflags", "+faststart", str(destino)],
                                capture_output=True, timeout=120)
        return juntar.returncode == 0

    def _baixar(self, job):
        camera = self.cameras[job["camera"]]
        caminho = camera.get("caminho_gravacao") or camera["caminho"]
        try:
            trechos = self._trechos_gravados(caminho, job["inicio"], job["inicio"] + job["duracao"])
        except (requests.RequestException, ValueError, KeyError):
            return False
        if not trechos:
            return False
        destino = self.pasta / f"ocorrencia{job['ocorrencia']}_{job['camera']}.mp4"
        with tempfile.TemporaryDirectory(dir=self.pasta) as temporaria:
            partes = []
            for numero, (inicio, duracao) in enumerate(trechos):
                parte = Path(temporaria) / f"{numero:03d}.mp4"
                if self._baixar_trecho(caminho, inicio, duracao, parte):
                    partes.append(parte)
            if not partes or not self._juntar(partes, destino, temporaria):
                return False
        relativo = str(destino.relative_to(self.raiz))
        self.banco.adicionar_clipe(job["ocorrencia"], relativo)
        self.notificar("clipe", {"ocorrencia": job["ocorrencia"], "clipe": relativo})
        log.info("clipe da ocorrência %s salvo (%s)", job["ocorrencia"], job["camera"])
        return True
