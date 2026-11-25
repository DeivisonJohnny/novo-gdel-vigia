import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from vigia.banco import Banco
from vigia.cadastro import CadastroCameras
from vigia.deteccao.analise import CameraAnalise
from vigia.web import criar_app
from vigia.web.contexto import Contexto

from apoio import url_do_banco_de_teste
from test_api import BaseApi

CAMERA = "bolognalife2"
LARGURA, ALTURA = 640, 480
MAQUININHA_ESQUERDA = [0.1, 0.5, 0.2, 0.7]
MAQUININHA_DIREITA = [0.7, 0.5, 0.8, 0.7]
TOTEM_DETECTADO = (300.0, 200.0, 340.0, 260.0)
PESSOA_NA_DIREITA = (440, 230, 520, 340)
PESSOA_NO_CENTRO = (290, 190, 350, 300)
PARAMETROS = {"totem_min_deteccoes": 12}


def analise_sem_modelo(pasta, maquininhas=None):
    analise = CameraAnalise.__new__(CameraAnalise)
    analise.nome, analise.p = CAMERA, PARAMETROS
    analise.camera = {"nome": CAMERA, "caminho": f"live/{CAMERA}", "cobre_totem": "auto"}
    analise.tamanho = (LARGURA, ALTURA)
    analise.eventos = []
    analise._registrar_evento = lambda t, pessoa, tipo, texto: analise.eventos.append(tipo)
    analise.totem_vistos = []
    analise._totem_novos = 0
    analise.arquivo_totem = Path(pasta) / "totem" / f"{CAMERA}.json"
    analise.totem_norm = analise._carregar_totem()
    analise.maquininhas = None
    analise.marcar_maquininhas(maquininhas)
    return analise


class MotorFalso:
    def __init__(self, analise):
        self.analises = {CAMERA: analise}

    def marcar_maquininhas(self, nome, caixas):
        self.analises[nome].marcar_maquininhas(caixas)


class AnaliseDaCamera(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def analise(self, maquininhas=None):
        return analise_sem_modelo(self.tmp.name, maquininhas)

    def ver_totem(self, analise, vezes=40):
        for _ in range(vezes):
            analise._observar_totens([TOTEM_DETECTADO])

    def test_sem_marcacao_aprende_o_totem_como_antes(self):
        analise = self.analise()
        self.assertEqual(analise.origem_totem, "procurando")
        self.ver_totem(analise)
        self.assertEqual(analise.origem_totem, "aprendido")
        self.assertTrue(analise.cobre_totem)
        self.assertTrue(analise.arquivo_totem.is_file())
        self.assertTrue(analise._perto_do_totem(PESSOA_NO_CENTRO))

    def test_marcacao_manual_para_o_aprendizado(self):
        analise = self.analise([MAQUININHA_ESQUERDA])
        self.ver_totem(analise)
        self.assertIsNone(analise.totem_norm)
        self.assertFalse(analise.arquivo_totem.exists())
        self.assertEqual(analise.totens, [MAQUININHA_ESQUERDA])
        self.assertEqual(analise.origem_totem, "manual")
        self.assertTrue(analise.cobre_totem)

    def test_passou_no_totem_usa_qualquer_area_marcada(self):
        analise = self.analise([MAQUININHA_ESQUERDA, MAQUININHA_DIREITA])
        self.assertTrue(analise._perto_do_totem(PESSOA_NA_DIREITA))
        self.assertFalse(analise._perto_do_totem(PESSOA_NO_CENTRO))

    def test_marcacao_manual_vale_mais_que_o_totem_aprendido(self):
        analise = self.analise()
        self.ver_totem(analise)
        aprendido = analise.totem_norm
        analise.marcar_maquininhas([MAQUININHA_DIREITA])
        self.ver_totem(analise, 200)
        self.assertEqual(analise.totem_norm, aprendido)
        self.assertEqual(analise.totens, [MAQUININHA_DIREITA])
        self.assertFalse(analise._perto_do_totem(PESSOA_NO_CENTRO))

    def test_sem_maquininha_descarta_o_totem_errado_e_para_de_aprender(self):
        analise = self.analise()
        self.ver_totem(analise)
        analise.marcar_maquininhas([])
        self.assertIsNone(analise.totem_norm)
        self.assertFalse(analise.arquivo_totem.exists())
        self.ver_totem(analise, 200)
        self.assertIsNone(analise.totem_norm)
        self.assertEqual(analise.totens, [])
        self.assertEqual(analise.origem_totem, "sem_maquininha")
        self.assertFalse(analise.cobre_totem)
        self.assertFalse(analise._perto_do_totem(PESSOA_NO_CENTRO))

    def test_voltar_ao_automatico_depois_de_sem_maquininha_aprende_do_zero(self):
        analise = self.analise([])
        analise.marcar_maquininhas(None)
        self.assertEqual(analise.origem_totem, "procurando")
        self.ver_totem(analise)
        self.assertEqual(analise.origem_totem, "aprendido")

    def test_remover_marcacao_volta_ao_automatico(self):
        analise = self.analise([MAQUININHA_DIREITA])
        analise.marcar_maquininhas(None)
        self.assertEqual(analise.origem_totem, "procurando")
        self.assertFalse(analise.cobre_totem)
        self.ver_totem(analise)
        self.assertEqual(analise.origem_totem, "aprendido")


class RotasDaMaquininha(BaseApi):
    def setUp(self):
        super().setUp()
        self.analise = analise_sem_modelo(self.pasta)
        self.cliente.app.state.contexto.motor = MotorFalso(self.analise)

    def marcar(self, caixas, camera=CAMERA):
        return self.cliente.put(f"/api/cameras/{camera}/maquininhas", json={"caixas": caixas})

    def test_admin_marca_e_a_analise_passa_a_usar_na_hora(self):
        self.entrar()
        resposta = self.marcar([MAQUININHA_ESQUERDA, MAQUININHA_DIREITA])
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["origem"], "manual")
        self.assertEqual(self.analise.totens, [MAQUININHA_ESQUERDA, MAQUININHA_DIREITA])
        self.assertEqual(self.banco.maquininhas_marcadas(), {CAMERA: [MAQUININHA_ESQUERDA, MAQUININHA_DIREITA]})

    def test_admin_edita_e_remove_e_volta_ao_automatico(self):
        self.entrar()
        self.marcar([MAQUININHA_ESQUERDA])
        self.marcar([MAQUININHA_DIREITA])
        self.assertEqual(self.cliente.get(f"/api/cameras/{CAMERA}/maquininhas").json()["manual"], [MAQUININHA_DIREITA])
        resposta = self.cliente.delete(f"/api/cameras/{CAMERA}/maquininhas")
        self.assertEqual(resposta.json(), {"camera": CAMERA, "origem": "automatica", "manual": None, "automatica": None})
        self.assertIsNone(self.analise.maquininhas)
        self.assertEqual(self.banco.maquininhas_marcadas(), {})

    def test_admin_indica_que_a_camera_nao_mostra_a_maquininha(self):
        self.entrar()
        resposta = self.cliente.put(f"/api/cameras/{CAMERA}/maquininhas/ausente")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["origem"], "sem_maquininha")
        self.assertIsNone(resposta.json()["manual"])
        self.assertEqual(self.analise.origem_totem, "sem_maquininha")
        self.assertEqual(self.banco.maquininhas_marcadas(), {CAMERA: []})
        self.cliente.delete(f"/api/cameras/{CAMERA}/maquininhas")
        self.assertEqual(self.analise.origem_totem, "procurando")

    def test_operador_nao_marca_nem_remove(self):
        self.entrar_como_operador()
        self.assertEqual(self.cliente.put(f"/api/cameras/{CAMERA}/maquininhas/ausente").status_code, 403)
        self.assertEqual(self.marcar([MAQUININHA_ESQUERDA]).status_code, 403)
        self.assertEqual(self.cliente.delete(f"/api/cameras/{CAMERA}/maquininhas").status_code, 403)
        self.assertEqual(self.cliente.get(f"/api/cameras/{CAMERA}/maquininhas").status_code, 403)
        self.assertIsNone(self.analise.maquininhas)

    def test_caixas_invalidas_sao_422(self):
        self.entrar()
        for caixas in ([], [[0.5, 0.5, 0.4, 0.6]], [[0.1, 0.1, 1.2, 0.3]], [[0.1, 0.2, 0.3]], [MAQUININHA_ESQUERDA] * 7):
            with self.subTest(caixas=caixas):
                self.assertEqual(self.marcar(caixas).status_code, 422)

    def test_camera_desconhecida_e_404(self):
        self.entrar()
        self.assertEqual(self.marcar([MAQUININHA_ESQUERDA], "nao-existe").status_code, 404)


class MarcacaoNoCadastro(BaseApi):
    def setUp(self):
        super().setUp()
        self.cliente.close()
        cadastro = CadastroCameras(self.cfg, self.banco)
        self.cliente = TestClient(criar_app(Contexto(self.cfg, self.banco, self.notificador, None, cadastro),
                                            pasta_frontend=self.pasta / "sem-frontend"))

    def test_listagem_mostra_a_marcacao_e_sobrevive_a_reinicio(self):
        self.entrar()
        self.cliente.put(f"/api/cameras/{CAMERA}/maquininhas", json={"caixas": [MAQUININHA_ESQUERDA]})
        cameras = {c["nome"]: c for c in self.cliente.get("/api/cameras/cadastro").json()["cameras"]}
        self.assertEqual(cameras[CAMERA]["maquininhas"], [MAQUININHA_ESQUERDA])
        self.assertIsNone(next(c for nome, c in cameras.items() if nome != CAMERA)["maquininhas"])
        reaberto = Banco(url_do_banco_de_teste())
        self.assertEqual(reaberto.maquininhas_marcadas(), {CAMERA: [MAQUININHA_ESQUERDA]})
        reaberto.fechar()


if __name__ == "__main__":
    unittest.main()
