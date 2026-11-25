import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from vigia.config import RAIZ, carregar, ligado

GERADOR = RAIZ.parent / "roteador" / "gerar.py"
SENHAS = {nome: "segredo-de-teste" for nome in ("CAM_BOLOGNALIFE2_SENHA", "CAM_BOLOGNALIFE2B_SENHA", "CAM_ITACOLOMI_SENHA",
                                                "CAM_ABBOTT1_SENHA", "CAM_ABBOTT2_SENHA", "LEITOR_SENHA")}


def gerar(*extras):
    with tempfile.TemporaryDirectory() as pasta:
        saida = Path(pasta) / "mediamtx.yml"
        subprocess.run([sys.executable, str(GERADOR), "--saida", str(saida), *extras], check=True, capture_output=True,
                       env={**os.environ, **SENHAS})
        return yaml.safe_load(saida.read_text())


def usuarios_any(mediamtx):
    return [u for u in mediamtx["authInternalUsers"] if u["user"] == "any"]


class RoteadorEmDocker(unittest.TestCase):
    def test_fora_do_docker_tudo_escuta_so_na_maquina(self):
        mediamtx = gerar()
        self.assertEqual(mediamtx["rtspAddress"], "127.0.0.1:8554")
        self.assertEqual(mediamtx["playbackAddress"], "127.0.0.1:9996")
        self.assertEqual([u["ips"] for u in usuarios_any(mediamtx)], [["127.0.0.1"]])

    def test_no_docker_so_o_backend_le_sem_senha_e_nao_publica(self):
        mediamtx = gerar("--docker", "--ip-backend=172.30.57.10", "--webrtc-udp=8289", "--webrtc-tcp=8290",
                         "--hosts-publicos=200.1.2.3, vigia.exemplo.com.br")
        self.assertEqual((mediamtx["rtspAddress"], mediamtx["apiAddress"], mediamtx["playbackAddress"]),
                         (":8554", ":9997", ":9996"))
        self.assertEqual([u["ips"] for u in usuarios_any(mediamtx)], [["127.0.0.1"], ["172.30.57.10"]])
        backend = usuarios_any(mediamtx)[1]
        self.assertEqual({p["action"] for p in backend["permissions"]}, {"read", "playback", "api"})
        self.assertEqual((mediamtx["webrtcLocalUDPAddress"], mediamtx["webrtcLocalTCPAddress"]), (":8289", ":8290"))
        self.assertEqual(mediamtx["webrtcAdditionalHosts"], ["200.1.2.3", "vigia.exemplo.com.br"])
        self.assertTrue(all(c.get("pass") for c in mediamtx["authInternalUsers"] if c["user"] != "any"))

    def test_docker_sem_ip_do_backend_e_recusado(self):
        resultado = subprocess.run([sys.executable, str(GERADOR), "--docker", "--saida", os.devnull],
                                   capture_output=True, env={**os.environ, **SENHAS})
        self.assertNotEqual(resultado.returncode, 0)


class AmbienteDeProducao(unittest.TestCase):
    def test_backend_fala_com_o_roteador_pelo_nome_do_servico(self):
        with mock.patch.dict(os.environ, {"VIGIA_COOKIE_SEGURO": "true", "VIGIA_REDE": "172.30.57.0/24"}):
            cfg = carregar(ambiente="prod-docker")
        self.assertEqual(cfg["servidor"]["host"], "0.0.0.0")
        self.assertTrue(ligado(cfg["servidor"]["cookie_seguro"]))
        self.assertEqual(cfg["servidor"]["proxies_confiaveis"], "172.30.57.0/24")
        self.assertEqual(cfg["cameras"]["abbott1"]["fonte"], "rtsp://roteador:8554/live/abbott1")
        self.assertEqual(cfg["cameras"]["abbott1"]["caminho_gravacao"], "gravacao/abbott1")

    def test_ambiente_remoto_le_o_roteador_de_producao_como_leitor(self):
        with mock.patch.dict(os.environ, {"VIGIA_LEITOR_SENHA": "senha-do-leitor", "DATABASE_URL": "postgresql://remoto/vigia"}):
            cfg = carregar(ambiente="remoto")
        self.assertEqual(cfg["cameras"]["abbott1"]["fonte"],
                         "rtmp://127.0.0.1:1945/live/abbott1?user=leitor&pass=senha-do-leitor")
        self.assertEqual(cfg["servidor"]["porta"], "8001")
        self.assertEqual(cfg["roteador"]["playback"], "")
        self.assertEqual(cfg["dados"]["banco"], "postgresql://remoto/vigia")

    def test_ligado_entende_texto_do_env(self):
        self.assertEqual([ligado(v) for v in ("true", "1", "sim", "false", "", "0", True, False, None)],
                         [True, True, True, False, False, False, True, False, False])


if __name__ == "__main__":
    unittest.main()
