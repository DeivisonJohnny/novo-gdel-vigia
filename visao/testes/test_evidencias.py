import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from vigia.config import carregar
from vigia.evidencias import RECUPERAR_ULTIMAS_S, Evidencias

from apoio import banco_de_teste
from test_fusao import configuracao_isolada


class CaminhoDaGravacao(unittest.TestCase):
    def test_roteador_de_producao_grava_em_gravacao(self):
        self.assertEqual(carregar(ambiente="dev")["cameras"]["abbott1"]["caminho_gravacao"], "gravacao/abbott1")

    def test_roteador_do_docker_grava_no_proprio_live(self):
        self.assertEqual(carregar(ambiente="docker")["cameras"]["abbott1"]["caminho_gravacao"], "live/abbott1")


class Recuperacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = configuracao_isolada(self.tmp.name)
        self.banco = banco_de_teste()
        self.evidencias = Evidencias(self.cfg, self.banco, self.cfg["dados"]["evidencias"])

    def tearDown(self):
        self.banco.fechar()
        self.tmp.cleanup()

    def ocorrencia(self, numero, cameras, criada_em, tipo="suspeita"):
        visita = {"id": f"v{numero}", "loja": "abbott", "inicio": criada_em - 60, "fim": criada_em, "cameras": cameras,
                  "pegadas": 1, "foi_totem": False, "score": 50, "nivel": "atencao", "pagamento_id": None,
                  "motivos": [], "grupo": [], "partes": []}
        self.banco.salvar_visita(visita)
        ocorrencia_id = self.banco.criar_ocorrencia(visita, [], tipo=tipo)
        self.banco._exec("UPDATE ocorrencias SET criada_em=%s WHERE id=%s", (criada_em, ocorrencia_id))
        return ocorrencia_id

    def test_ocorrencias_recentes_sem_video_voltam_para_a_fila(self):
        agora = time.time()
        recente = self.ocorrencia(1, ["abbott1", "abbott2"], agora - 3600)
        com_video = self.ocorrencia(2, ["abbott1"], agora - 600)
        self.banco.adicionar_clipe(com_video, "clipes/ocorrencia2_abbott1.mp4")
        self.ocorrencia(3, ["abbott1"], agora - RECUPERAR_ULTIMAS_S - 60)
        self.ocorrencia(4, ["camera_removida"], agora - 60)
        self.evidencias.recuperar_pendentes(agora)
        pedidos = [(job["ocorrencia"], job["camera"]) for job in self.evidencias.fila]
        self.assertEqual(pedidos, [(recente, "abbott1"), (recente, "abbott2")])
        job = self.evidencias.fila[0]
        self.assertAlmostEqual(job["inicio"], agora - 3600 - 60 - 8, places=3)

    def test_entrada_sem_compra_recorta_todas_as_cameras_da_loja(self):
        agora = time.time()
        self.evidencias.pedir_clipes(1, SimpleNamespace(inicio=agora - 60, fim=agora, cameras=["abbott1"], loja="abbott"),
                                     todas_da_loja=True)
        self.assertEqual([job["camera"] for job in self.evidencias.fila], ["abbott1", "abbott2"])

    def test_suspeita_recorta_so_as_cameras_em_que_a_pessoa_apareceu(self):
        agora = time.time()
        self.evidencias.pedir_clipes(1, SimpleNamespace(inicio=agora - 60, fim=agora, cameras=["abbott1"], loja="abbott"))
        self.assertEqual([job["camera"] for job in self.evidencias.fila], ["abbott1"])

    def test_recuperacao_de_entrada_sem_compra_volta_com_todas_as_cameras(self):
        agora = time.time()
        sem_compra = self.ocorrencia(1, ["abbott1"], agora - 600, tipo="sem_compra")
        self.evidencias.recuperar_pendentes(agora)
        self.assertEqual([(job["ocorrencia"], job["camera"]) for job in self.evidencias.fila],
                         [(sem_compra, "abbott1"), (sem_compra, "abbott2")])


if __name__ == "__main__":
    unittest.main()
