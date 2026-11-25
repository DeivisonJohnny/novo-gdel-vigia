import logging
import re
import threading
import time
from datetime import datetime

from .config import caminho_projeto
from .evidencias import MARGEM_S, RECUPERAR_ULTIMAS_S

log = logging.getLogger(__name__)

INICIO_NO_NOME = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})-(\d+)([+-]\d{4})")
EXTENSOES_DE_GRAVACAO = {".mp4", ".ts"}


def inicio_do_segmento(arquivo):
    achado = INICIO_NO_NOME.search(arquivo.stem)
    if not achado:
        return None
    data, fracao, fuso = achado.groups()
    return datetime.strptime(data + fuso, "%Y-%m-%d_%H-%M-%S%z").timestamp() + float("0." + fracao)


def sobrepoe(inicio, fim, janelas):
    return any(inicio <= fim_da_janela and fim >= inicio_da_janela for inicio_da_janela, fim_da_janela in janelas)


def segmentos_fechados(pasta):
    por_camera = {}
    for arquivo in pasta.rglob("*"):
        if arquivo.suffix in EXTENSOES_DE_GRAVACAO and arquivo.is_file():
            por_camera.setdefault(arquivo.parent, []).append(arquivo)
    for arquivos in por_camera.values():
        sendo_gravado = max(arquivos, key=lambda a: a.stat().st_mtime)
        yield from (a for a in arquivos if a != sendo_gravado)


class Retencao:
    def __init__(self, cfg, banco, inicio_em_andamento=lambda: None):
        g = cfg.get("gravacoes") or {}
        self.pasta = caminho_projeto(g["pasta"]) if g.get("pasta") else None
        self.intervalo_s = g.get("limpar_a_cada_min", 5) * 60
        self.banco = banco
        self.inicio_em_andamento = inicio_em_andamento
        self.ativa = bool(self.pasta and cfg["roteador"].get("playback"))
        self.ultima = {"apagados": 0, "bytes": 0, "em": None}

    def iniciar(self):
        if self.ativa:
            log.info("limpeza de gravações ligada em %s: só fica o que alguma ocorrência usa", self.pasta)
            threading.Thread(target=self._rodar, name="retencao", daemon=True).start()
        return self

    def _rodar(self):
        while True:
            time.sleep(self.intervalo_s)
            try:
                self.limpar()
            except OSError as erro:
                log.warning("não consegui limpar as gravações: %s", erro)

    def janelas_a_manter(self, agora):
        janelas = [(inicio - MARGEM_S, fim + MARGEM_S)
                   for inicio, fim in self.banco.periodos_das_ocorrencias(agora - RECUPERAR_ULTIMAS_S)]
        em_andamento = self.inicio_em_andamento()
        if em_andamento is not None:
            janelas.append((em_andamento - MARGEM_S, agora))
        return janelas

    def limpar(self, agora=None):
        agora = agora or time.time()
        if not self.pasta or not self.pasta.is_dir():
            return self.ultima
        janelas = self.janelas_a_manter(agora)
        apagados, liberados = 0, 0
        for arquivo in segmentos_fechados(self.pasta):
            estado = arquivo.stat()
            if sobrepoe(inicio_do_segmento(arquivo) or estado.st_mtime, estado.st_mtime, janelas):
                continue
            arquivo.unlink(missing_ok=True)
            apagados += 1
            liberados += estado.st_size
        if apagados:
            log.info("%s gravação(ões) sem ocorrência apagada(s), %.1f MB liberados", apagados, liberados / 1e6)
        self.ultima = {"apagados": apagados, "bytes": liberados, "em": agora}
        return self.ultima
