import logging
import shutil
import threading
import time

from .config import caminho_projeto, pdvs_da_loja
from .deteccao.marcacao import origem_da_marcacao
from .deteccao.coleta import Coleta
from .deteccao.fonte import Fonte
from .evidencias import Evidencias
from .retencao import Retencao
from .fusao import Fusao
from .touchpay import TouchPay
from .triagem import Triagem

log = logging.getLogger(__name__)

INTERVALO_FUSAO_S = 1.0
ESPERA_SEM_TRABALHO_S = 0.01


class Motor:
    def __init__(self, cfg, banco, notificador, cameras=None):
        self.cfg = cfg
        self.banco = banco
        self.notificador = notificador
        self.nomes = cameras or list(cfg["cameras"])
        self.evidencias = Evidencias(cfg, banco, cfg["dados"]["evidencias"], notificador.publicar)
        self.triagem = Triagem(cfg, banco, notificador.publicar)
        self.fusao = Fusao(cfg, banco, self.evidencias, notificador.publicar, self.triagem)
        self.retencao = Retencao(cfg, banco, self.inicio_mais_antigo_em_andamento)
        self.touchpay = TouchPay(cfg, banco)
        self.coleta = Coleta(cfg.get("coleta"), cfg["dados"]["treino"])
        self.modelo = None
        self.analises = {}
        self.fontes = {}
        self.situacao = "parado"
        self.erro = ""
        self.iniciado_em = None
        self._parar = threading.Event()
        self._lock_cameras = threading.RLock()
        self.fusao.cobre_totem = self._camera_cobre_totem

    def _camera_cobre_totem(self, nome):
        analise = self.analises.get(nome)
        return analise.cobre_totem if analise else False

    def iniciar(self):
        self.iniciado_em = time.time()
        self.touchpay.iniciar()
        self.evidencias.iniciar()
        self.retencao.iniciar()
        self.triagem.iniciar()
        for loja in sorted({self.cfg["cameras"][n].get("loja") for n in self.nomes}):
            if not pdvs_da_loja(self.cfg, loja):
                log.warning("loja %s sem PDV TouchPay: suspeitas dessa loja ficam no máximo em atenção", loja)
        threading.Thread(target=self._rodar, name="motor", daemon=True).start()
        return self

    def _carregar(self):
        from .deteccao.modelo import Modelo

        p = self.cfg["visao"]
        self.situacao = "carregando modelo"
        modelo = Modelo(p, caminho_projeto(p["modelo"]))
        with self._lock_cameras:
            for nome in self.nomes:
                self._ligar_camera(nome)
            self.modelo = modelo

    def _ligar_camera(self, nome):
        from .deteccao.analise import CameraAnalise

        p = self.cfg["visao"]
        camera = self.cfg["cameras"][nome]
        self.fontes[nome] = Fonte(nome, camera["fonte"], p["fps_analise"], p["largura_analise"]).iniciar()
        self.analises[nome] = CameraAnalise(camera, p, self.cfg["dados"]["evidencias"], self.cfg["dados"]["totem"],
                                            self.fusao.adicionar, self._evento_camera, self.coleta,
                                            self.banco.maquininhas_marcadas().get(nome))

    def adicionar_camera(self, nome):
        with self._lock_cameras:
            if nome in self.nomes:
                return
            self.nomes.append(nome)
            self.fusao.loja_da_camera[nome] = self.cfg["cameras"][nome].get("loja")
            self.touchpay.atualizar_lojas(self.cfg)
            if self.modelo:
                self._ligar_camera(nome)
        log.info("câmera %s adicionada à detecção", nome)

    def remover_camera(self, nome):
        with self._lock_cameras:
            if nome not in self.nomes:
                return
            self.nomes.remove(nome)
            self.analises.pop(nome, None)
            fonte = self.fontes.pop(nome, None)
        if fonte:
            fonte.parar()
        log.info("câmera %s removida da detecção", nome)

    def marcar_maquininhas(self, nome, caixas):
        analise = self.analises.get(nome)
        if analise:
            analise.marcar_maquininhas(caixas)

    def _evento_camera(self, evento):
        self.notificador.publicar("evento_camera", evento)

    def _rodar(self):
        try:
            self._carregar()
        except BaseException as erro:
            self.situacao = "erro"
            self.erro = str(erro)
            log.error("motor de detecção não iniciou: %s", erro)
            return
        self.situacao = "rodando"
        log.info("detecção rodando em %s", ", ".join(self.nomes))
        ultima_fusao = 0.0
        while not self._parar.is_set():
            trabalhou = self._processar_quadros()
            agora = time.time()
            if agora - ultima_fusao >= INTERVALO_FUSAO_S:
                ultima_fusao = agora
                self.fusao.tick(agora)
            if self.fontes and all(f.terminou for f in list(self.fontes.values())):
                self._encerrar_videos(agora)
                return
            if not trabalhou:
                time.sleep(ESPERA_SEM_TRABALHO_S)

    def _processar_quadros(self):
        trabalhou = False
        for nome, analise in list(self.analises.items()):
            fonte = self.fontes.get(nome)
            if not fonte:
                continue
            seq, frame, t = fonte.ultimo()
            if frame is None or seq == analise.seq_processado:
                continue
            analise.seq_processado = seq
            analise.processar(frame, t, self.modelo)
            trabalhou = True
        return trabalhou

    def _encerrar_videos(self, agora):
        for analise in self.analises.values():
            analise.finalizar_todas(agora + 3600)
        self.fusao.tick(agora + 3600 + self.cfg["fusao"]["aguardar_pagamento_s"] * 2)
        self.situacao = "vídeos de teste concluídos"
        log.info("vídeos de teste terminaram")

    def parar(self):
        self._parar.set()
        self.triagem.parar()
        for fonte in list(self.fontes.values()):
            fonte.parar()

    def inicio_mais_antigo_em_andamento(self):
        inicios = [a.inicio_mais_antigo_em_andamento() for a in list(self.analises.values())]
        inicios.append(self.fusao.inicio_mais_antigo_pendente())
        return min((i for i in inicios if i is not None), default=None)

    def cameras(self):
        return [self._status_camera(nome) for nome in list(self.nomes) if nome in self.cfg["cameras"]]

    def _status_camera(self, nome):
        camera = self.cfg["cameras"][nome]
        analise = self.analises.get(nome)
        if analise:
            return analise.status(self.fontes.get(nome))
        marcadas = self.banco.maquininhas_marcadas().get(nome)
        return {"nome": nome, "descricao": camera.get("descricao", nome), "loja": camera.get("loja"), "online": False,
                "erro": self.situacao, "fps": 0, "uso_ia": 0, "pessoas": 0, "cobre_totem": bool(marcadas),
                "origem_totem": origem_da_marcacao(marcadas, sem_marcacao="procurando"), "totens": marcadas or [],
                "caminho": camera["caminho"], "eventos": []}

    def status(self):
        disco = shutil.disk_usage(self.cfg["dados"]["evidencias"])
        return {
            "situacao": self.situacao,
            "erro": self.erro,
            "iniciado_em": self.iniciado_em,
            "modelo": self.modelo.status() if self.modelo else None,
            "touchpay": self.touchpay.status(),
            "coleta": self.coleta.status(),
            "visitas_em_andamento": self.fusao.estado(),
            "disco": {"livre_gb": round(disco.free / 1e9, 1), "total_gb": round(disco.total / 1e9, 1)},
            "clipes_ativos": self.evidencias.ativo,
            "triagem": self.triagem.status(),
        }
