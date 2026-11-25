import hashlib
import secrets
import tempfile
import time
import unittest
from base64 import b64encode
from pathlib import Path

from fastapi.testclient import TestClient

from vigia.notificacoes import Notificador
from vigia.web import criar_app
from vigia.web.contexto import COOKIE_SESSAO, Contexto
from vigia.cadastro import CadastroCameras, _assinatura_usuarios
from vigia.config import aplicar_cadastros, carregar, pdvs_da_loja

from apoio import banco_de_teste, url_do_banco_de_teste

SENHA_ADMIN = "admin-forte-123"
SENHA_OPERADOR = "operador-forte-123"
DURACAO_SESSAO_S = 12 * 3600
CUSTO_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}


def gerar_hash(senha):
    sal = secrets.token_bytes(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, **CUSTO_SCRYPT)
    return "scrypt$" + b64encode(sal).decode() + "$" + b64encode(chave).decode()


def hash_do_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def configuracao_isolada(pasta):
    cfg = carregar(ambiente="dev")
    cfg["sistema"]["fuso"] = "America/Sao_Paulo"
    cfg["servidor"]["cookie_seguro"] = False
    for loja in cfg["lojas"].values():
        loja["pdv"] = ""
    cfg["lojas"]["bologna"]["pdv"] = "42"
    cfg["dados"] = {chave: str(Path(pasta) / chave) for chave in ("evidencias", "totem", "treino")}
    cfg["dados"]["banco"] = url_do_banco_de_teste()
    return cfg


class BaseApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.cfg = configuracao_isolada(self.tmp.name)
        self.banco = banco_de_teste()
        self.notificador = Notificador()
        self.admin_id = self.criar_usuario("Admin", "admin@vigia.local", SENHA_ADMIN, "admin")
        self.operador_id = self.criar_usuario("Operador", "operador@vigia.local", SENHA_OPERADOR, "operador")
        app = criar_app(Contexto(self.cfg, self.banco, self.notificador, None), pasta_frontend=self.pasta / "sem-frontend")
        self.cliente = TestClient(app)

    def tearDown(self):
        self.cliente.close()
        self.banco.fechar()
        self.tmp.cleanup()

    def criar_usuario(self, nome, email, senha, papel):
        linha = self.banco._um(
            "INSERT INTO usuarios (nome, email, senha, papel, ativo, criado_em) VALUES (%s, %s, %s, %s, true, %s) RETURNING id",
            (nome, email, gerar_hash(senha), papel, time.time()))
        return linha["id"]

    def entrar(self, email="admin@vigia.local", senha=SENHA_ADMIN):
        usuario_id = self.admin_id if email == "admin@vigia.local" else self.operador_id
        token = secrets.token_urlsafe(32)
        agora = time.time()
        self.banco._exec(
            "INSERT INTO sessoes (token, usuario_id, criada_em, expira_em) VALUES (%s, %s, %s, %s)",
            (hash_do_token(token), usuario_id, agora, agora + DURACAO_SESSAO_S))
        self.cliente.cookies.set(COOKIE_SESSAO, token)
        return self.cliente.get("/api/config-publica")

    def entrar_como_operador(self):
        return self.entrar("operador@vigia.local", SENHA_OPERADOR)

    def criar_ocorrencia_com_venda_proxima(self):
        agora = time.time()
        visita = {"id": "20261109-120000-1", "loja": "bologna", "inicio": agora - 60, "fim": agora, "cameras": ["bolognalife2"],
                  "pegadas": 1, "foi_totem": False, "score": 70, "nivel": "alerta", "pagamento_id": None,
                  "motivos": [{"sinal": "sem_pagamento", "peso": 60, "texto": "pegou 1x e não há pagamento"}],
                  "grupo": [], "partes": [{"camera": "bolognalife2", "id": "p1", "inicio": agora - 60, "fim": agora,
                                           "pegadas": [agora - 30], "totem": [], "saiu_com_produto": True}]}
        self.banco.salvar_visita(visita)
        self.banco.salvar_pagamento({"id": "venda-1", "horario": agora + 30, "valor": 9.5, "situacao": "aprovado",
                                     "qtd_itens": 1, "pdv": "42", "loja": "bologna", "metodo": "Credit",
                                     "itens": [{"produto_id": 1, "descricao": "Coca 350", "quantidade": 1, "preco": 9.5}]})
        return self.banco.criar_ocorrencia(visita, ["bolognalife2/p1_pegou1.jpg"])


class SemSessao(BaseApi):
    def test_rotas_protegidas_exigem_sessao(self):
        for rota in ("/api/painel", "/api/ocorrencias", "/api/visitas", "/api/vendas",
                     "/api/sistema", "/api/arquivos/qualquer.jpg"):
            with self.subTest(rota=rota):
                self.assertEqual(self.cliente.get(rota).status_code, 401)

    def test_cookie_invalido_nao_autentica(self):
        self.cliente.cookies.set(COOKIE_SESSAO, "token-inventado")
        self.assertEqual(self.cliente.get("/api/painel").status_code, 401)

    def test_config_publica_e_aberta_e_tem_cabecalhos_de_seguranca(self):
        resposta = self.cliente.get("/api/config-publica")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["ambiente"], "dev")
        self.assertEqual(resposta.headers["x-frame-options"], "DENY")
        self.assertEqual(resposta.headers["x-content-type-options"], "nosniff")


class Sessao(BaseApi):
    def test_sem_cookie_e_401(self):
        self.assertEqual(self.cliente.get("/api/painel").status_code, 401)

    def test_sessao_valida_libera_acesso(self):
        self.entrar()
        self.assertEqual(self.cliente.get("/api/painel").status_code, 200)

    def test_sessao_expirada_e_401(self):
        token = secrets.token_urlsafe(32)
        agora = time.time()
        self.banco._exec("INSERT INTO sessoes (token, usuario_id, criada_em, expira_em) VALUES (%s, %s, %s, %s)",
                         (hash_do_token(token), self.admin_id, agora - 100, agora - 1))
        self.cliente.cookies.set(COOKIE_SESSAO, token)
        self.assertEqual(self.cliente.get("/api/painel").status_code, 401)

    def test_usuario_desativado_perde_acesso(self):
        self.entrar()
        self.banco._exec("UPDATE usuarios SET ativo=false WHERE id=%s", (self.admin_id,))
        self.assertEqual(self.cliente.get("/api/painel").status_code, 401)


class Permissoes(BaseApi):
    def test_operador_nao_acessa_rotas_de_admin(self):
        self.entrar_como_operador()
        self.assertEqual(self.cliente.get("/api/sistema").status_code, 403)
        self.assertEqual(self.cliente.get("/api/cameras/cadastro").status_code, 403)

    def test_operador_acessa_painel_e_ocorrencias(self):
        self.entrar_como_operador()
        painel = self.cliente.get("/api/painel")
        self.assertEqual(painel.status_code, 200)
        self.assertEqual(painel.json()["motor"], "desligado")
        self.assertEqual(self.cliente.get("/api/ocorrencias").json()["total"], 0)

    def test_admin_acessa_sistema(self):
        self.entrar()
        resposta = self.cliente.get("/api/sistema")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["motor"], {"situacao": "desligado"})


class Arquivos(BaseApi):
    def setUp(self):
        super().setUp()
        evidencias = Path(self.cfg["dados"]["evidencias"])
        (evidencias / "bolognalife2").mkdir(parents=True)
        (evidencias / "bolognalife2" / "p1_pegou1.jpg").write_bytes(b"\xff\xd8\xff\xe0jpeg")
        (evidencias / "anotacao.txt").write_text("texto")
        (self.pasta / "fora.jpg").write_bytes(b"\xff\xd8\xff\xe0fora")
        self.entrar_como_operador()

    def test_jpg_dentro_das_evidencias_e_servido(self):
        resposta = self.cliente.get("/api/arquivos/bolognalife2/p1_pegou1.jpg")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers["content-type"], "image/jpeg")
        self.assertEqual(resposta.content, b"\xff\xd8\xff\xe0jpeg")

    def test_extensao_fora_da_lista_e_404(self):
        self.assertEqual(self.cliente.get("/api/arquivos/anotacao.txt").status_code, 404)

    def test_arquivo_inexistente_e_404(self):
        self.assertEqual(self.cliente.get("/api/arquivos/bolognalife2/nao-existe.jpg").status_code, 404)

    def test_path_traversal_e_404(self):
        for caminho in ("../vigia.db", "../fora.jpg", "%2e%2e/vigia.db", "%2e%2e/fora.jpg", "..%2ffora.jpg",
                        "%2e%2e%2ffora.jpg", "bolognalife2/..%2f..%2ffora.jpg", "%2F" + str(self.pasta / "fora.jpg").lstrip("/"),
                        "..%5cfora.jpg"):
            with self.subTest(caminho=caminho):
                resposta = self.cliente.get("/api/arquivos/" + caminho)
                self.assertEqual(resposta.status_code, 404)
                self.assertNotIn(b"fora", resposta.content)


class AnaliseFalsa:
    def __init__(self, jpeg):
        self.jpeg = jpeg
        self.deteccao = None

    def jpeg_atual(self):
        return self.jpeg


class QuadroDaCamera(BaseApi):
    def setUp(self):
        super().setUp()
        motor = type("MotorFalso", (), {"analises": {"bolognalife2": AnaliseFalsa(b"\xff\xd8quadro"),
                                                     "itacolomi": AnaliseFalsa(None)}})()
        self.cliente.app.state.contexto.motor = motor
        self.entrar_como_operador()

    def test_devolve_um_unico_jpeg_sem_cache(self):
        resposta = self.cliente.get("/api/cameras/bolognalife2/quadro")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers["content-type"], "image/jpeg")
        self.assertEqual(resposta.headers["cache-control"], "no-store")
        self.assertEqual(resposta.content, b"\xff\xd8quadro")

    def test_camera_sem_imagem_ainda_e_503(self):
        self.assertEqual(self.cliente.get("/api/cameras/itacolomi/quadro").status_code, 503)

    def test_camera_desconhecida_e_404(self):
        self.assertEqual(self.cliente.get("/api/cameras/nao-existe/quadro").status_code, 404)

    def test_exige_sessao(self):
        self.cliente.cookies.clear()
        self.assertEqual(self.cliente.get("/api/cameras/bolognalife2/quadro").status_code, 401)


class Ocorrencias(BaseApi):
    def setUp(self):
        super().setUp()
        self.ocorrencia_id = self.criar_ocorrencia_com_venda_proxima()
        self.entrar_como_operador()

    def test_lista_ocorrencias_com_nome_da_loja_e_contagem_de_abertas(self):
        dados = self.cliente.get("/api/ocorrencias").json()
        self.assertEqual((dados["total"], dados["abertas"]), (1, 1))
        self.assertEqual(dados["itens"][0]["loja_nome"], "Bologna Life")
        self.assertEqual(dados["itens"][0]["cameras"], ["bolognalife2"])

    def test_detalhe_traz_vendas_proximas_com_itens_em_lista(self):
        resposta = self.cliente.get(f"/api/ocorrencias/{self.ocorrencia_id}")
        self.assertEqual(resposta.status_code, 200)
        detalhe = resposta.json()
        self.assertEqual([v["id"] for v in detalhe["vendas_proximas"]], ["venda-1"])
        itens = detalhe["vendas_proximas"][0]["itens"]
        self.assertIsInstance(itens, list)
        self.assertEqual(itens[0]["descricao"], "Coca 350")
        self.assertIsNone(detalhe["pagamento"])
        self.assertEqual([e["tipo"] for e in detalhe["linha_do_tempo"]], ["entrou", "pegou", "saiu"])

    def test_ocorrencia_inexistente_e_404(self):
        self.assertEqual(self.cliente.get("/api/ocorrencias/9999").status_code, 404)
        self.assertEqual(self.cliente.post("/api/ocorrencias/9999/revisao", json={"veredito": "furto"}).status_code, 404)

    def test_revisao_grava_veredito_e_marca_revisada(self):
        resposta = self.cliente.post(f"/api/ocorrencias/{self.ocorrencia_id}/revisao",
                                     json={"veredito": "furto", "observacao": "  levou sem pagar  "})
        self.assertEqual(resposta.status_code, 200)
        revisada = resposta.json()
        self.assertEqual((revisada["veredito"], revisada["situacao"]), ("furto", "revisada"))
        self.assertEqual((revisada["observacao"], revisada["revisada_por"]), ("levou sem pagar", "Operador"))
        self.assertIsInstance(revisada["vendas_proximas"][0]["itens"], list)
        self.assertEqual(self.cliente.get("/api/ocorrencias").json()["abertas"], 0)
        self.assertIn("ocorrencia_revisada", [m["tipo"] for m in self.notificador.depois_de(0)])

    def test_veredito_invalido_e_422(self):
        resposta = self.cliente.post(f"/api/ocorrencias/{self.ocorrencia_id}/revisao", json={"veredito": "talvez"})
        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(self.banco.ocorrencia(self.ocorrencia_id)["situacao"], "aberta")


class FrontendServido(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pasta = Path(self.tmp.name)
        self.frontend = pasta / "dist"
        (self.frontend / "assets").mkdir(parents=True)
        (self.frontend / "index.html").write_text("<html>vigia</html>")
        cfg = configuracao_isolada(self.tmp.name)
        self.banco = banco_de_teste()
        self.cliente = TestClient(criar_app(Contexto(cfg, self.banco, Notificador(), None), pasta_frontend=self.frontend))

    def tearDown(self):
        self.cliente.close()
        self.banco.fechar()
        self.tmp.cleanup()

    def test_rotas_do_spa_devolvem_o_index(self):
        resposta = self.cliente.get("/ocorrencias/1")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("vigia", resposta.text)

    def test_rota_de_api_inexistente_nao_cai_no_spa(self):
        for rota in ("/api/nao-existe", "/api/arquivos/../vigia.db", "/api"):
            with self.subTest(rota=rota):
                self.assertEqual(self.cliente.get(rota).status_code, 404)

    def test_spa_nao_serve_arquivo_fora_da_pasta(self):
        resposta = self.cliente.get("/%2e%2e/vigia.db")
        self.assertNotIn(b"SQLite", resposta.content)


class CadastroDeCameras(BaseApi):
    def setUp(self):
        super().setUp()
        self.cliente.close()
        self.cfg["roteador"]["api"] = ""
        self.cfg["roteador"]["rtmp_publico"] = "rtmp://200.1.2.3:1945"
        cadastro = CadastroCameras(self.cfg, self.banco)
        app = criar_app(Contexto(self.cfg, self.banco, self.notificador, None, cadastro), pasta_frontend=self.pasta / "sem-frontend")
        self.cliente = TestClient(app)

    def cadastrar(self, **dados):
        return self.cliente.post("/api/cameras/cadastro", json={"codigo": "XTPRZS54", **dados})

    def test_cadastro_com_loja_nova_devolve_url_rtmp_completa(self):
        self.entrar()
        resposta = self.cadastrar(nova_loja={"nome": "Santa Terezinha", "pdv": ""})
        self.assertEqual(resposta.status_code, 201)
        corpo = resposta.json()
        self.assertTrue(corpo["url"].startswith("rtmp://200.1.2.3:1945/live/xtprzs54?user=xtprzs54&pass="))
        self.assertFalse(corpo["roteador_ok"])
        self.assertEqual(self.cfg["cameras"]["xtprzs54"]["loja"], "santa-terezinha")
        lojas = {loja["id"] for loja in self.cliente.get("/api/lojas").json()}
        self.assertIn("santa-terezinha", lojas)

    def test_cadastro_sobrevive_a_reinicio(self):
        self.entrar()
        self.cadastrar(loja="bologna")
        cfg = configuracao_isolada(self.tmp.name)
        aplicar_cadastros(cfg, self.banco)
        self.assertEqual(cfg["cameras"]["xtprzs54"]["caminho"], "live/xtprzs54")

    def test_codigo_repetido_e_recusado(self):
        self.entrar()
        self.cadastrar(loja="bologna")
        self.assertEqual(self.cadastrar(loja="bologna").status_code, 409)
        self.assertEqual(self.cliente.post("/api/cameras/cadastro", json={"codigo": "abbott1", "loja": "abbott"}).status_code, 409)

    def test_listagem_mostra_url_so_das_cadastradas_e_remove(self):
        self.entrar()
        self.cadastrar(loja="bologna")
        cameras = {c["nome"]: c for c in self.cliente.get("/api/cameras/cadastro").json()["cameras"]}
        self.assertIsNone(cameras["abbott1"]["url"])
        self.assertIn("pass=", cameras["xtprzs54"]["url"])
        self.assertEqual(self.cliente.delete("/api/cameras/cadastro/abbott1").status_code, 404)
        self.assertEqual(self.cliente.delete("/api/cameras/cadastro/xtprzs54").status_code, 200)
        self.assertNotIn("xtprzs54", self.cfg["cameras"])

    def test_operador_nao_cadastra(self):
        self.entrar_como_operador()
        self.assertEqual(self.cadastrar(loja="bologna").status_code, 403)


class AssinaturaDeUsuariosDoRoteador(unittest.TestCase):
    def test_ip_sem_mascara_equivale_ao_devolvido_pela_api(self):
        do_arquivo = [{"user": "any", "pass": "", "ips": ["127.0.0.1"], "permissions": [{"action": "read"}]}]
        da_api = [{"user": "any", "pass": "<redacted>", "ips": ["127.0.0.1/32"], "permissions": [{"action": "read"}]}]
        self.assertEqual(_assinatura_usuarios(do_arquivo), _assinatura_usuarios(da_api))


class PdvDaLojaPeloPainel(CadastroDeCameras):
    def test_definir_pdv_de_loja_nova_vale_na_hora_e_apos_reinicio(self):
        self.entrar()
        self.cadastrar(nova_loja={"nome": "Evertec", "pdv": ""})
        self.assertEqual(self.cliente.put("/api/cameras/lojas/evertec/pdv", json={"pdv": "321"}).status_code, 200)
        self.assertEqual(pdvs_da_loja(self.cfg, "evertec"), ["321"])
        cfg = configuracao_isolada(self.tmp.name)
        aplicar_cadastros(cfg, self.banco)
        self.assertEqual(pdvs_da_loja(cfg, "evertec"), ["321"])

    def test_pdv_so_aceita_numeros_e_loja_existente(self):
        self.entrar()
        self.assertEqual(self.cliente.put("/api/cameras/lojas/bologna/pdv", json={"pdv": "abc"}).status_code, 422)
        self.assertEqual(self.cliente.put("/api/cameras/lojas/nao-existe/pdv", json={"pdv": "1"}).status_code, 404)

    def test_sem_motor_lista_de_pdvs_vem_vazia(self):
        self.entrar()
        self.assertEqual(self.cliente.get("/api/cameras/pdvs-touchpay").json(), [])


if __name__ == "__main__":
    unittest.main()
