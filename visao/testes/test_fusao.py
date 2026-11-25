import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from vigia.config import carregar
from vigia.deteccao.analise import CameraAnalise, PessoaCamera
from vigia.fusao import Fusao
from vigia.touchpay import TouchPay

from apoio import banco_de_teste, url_do_banco_de_teste

T0 = 1_800_000_000.0
ROUPA_AZUL = np.zeros(128, np.float32)
ROUPA_AZUL[10] = 1
ROUPA_VERMELHA = np.zeros(128, np.float32)
ROUPA_VERMELHA[100] = 1


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def venda(quando, itens=1, ident=None, metodo="Credit", pdv=42):
    return {"uuid": ident or f"00000000-0000-0000-0000-{int(quando * 1000):012d}", "paymentMethod": metodo,
            "totalPrice": 10.0, "paymentAmount": 9.5, "pointOfSaleId": pdv, "date": iso(T0 + quando),
            "userInfo": {"document": "123.456.789-00", "email": "x@y.com", "phoneNumber": "11999999999"},
            "items": [{"productId": 1, "productDescription": "Coca 350", "quantity": 1, "price": 9.5}] * itens}


def pessoa(camera="bolognalife2", inicio=0, fim=60, pegadas=(), totem=(), roupa=None, ident=None):
    p = PessoaCamera(camera, ident or f"{camera}-{inicio}-{fim}", T0 + inicio, T0 + fim)
    p.pegadas = [T0 + t for t in pegadas]
    p.totem = [[T0 + a, T0 + b] for a, b in totem]
    p.ids_rastreador = {1}
    if roupa is not None:
        p.somar_hist(roupa)
    return p


def sinais(resultado):
    return [m["sinal"] for m in resultado["motivos"]]


def configuracao_isolada(pasta):
    cfg = carregar(ambiente="dev")
    cfg["sistema"]["fuso"] = "America/Sao_Paulo"
    cfg["touchpay"]["fuso_api"] = "America/Sao_Paulo"
    cfg["touchpay"]["autenticacao"] = {}
    cfg["lojas"]["vguard"] = {"nome": "V-Guard"}
    cfg["cameras"]["vguard"] = {"nome": "vguard", "descricao": "V-Guard", "caminho": "live/vguard", "loja": "vguard",
                                "fonte": "rtsp://127.0.0.1:8554/live/vguard"}
    for loja in cfg["lojas"].values():
        loja["pdv"] = ""
    cfg["lojas"]["bologna"]["pdv"] = "42"
    cfg["lojas"]["vguard"]["pdv"] = "77"
    for camera in cfg["cameras"].values():
        camera["cobre_totem"] = False
    cfg["cameras"]["bolognalife2"]["cobre_totem"] = True
    cfg["dados"] = {chave: str(Path(pasta) / chave) for chave in ("evidencias", "totem", "treino")}
    cfg["dados"]["banco"] = url_do_banco_de_teste()
    return cfg


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = configuracao_isolada(self.tmp.name)
        self.banco = banco_de_teste()
        self.notificacoes = []
        self.fusao = Fusao(self.cfg, self.banco, notificar=lambda tipo, dados: self.notificacoes.append((tipo, dados)))
        self.fusao._ultima_revisao = float("inf")
        self.tp = TouchPay(self.cfg, self.banco)

    def tearDown(self):
        self.banco.fechar()
        self.tmp.cleanup()

    def pagar(self, quando, itens=1, ident=None, metodo="Credit", pdv=42):
        self.tp.registrar([venda(quando, itens, ident, metodo, pdv)])

    def operador(self, quando, tipo="Repositioning", usuario="repositor@loja"):
        self.banco.salvar_movimentacoes([self.tp.normalizar_movimentacao(
            {"id": int(quando * 10), "date": iso(T0 + quando), "type": tipo, "productId": 1, "changeAmount": 5,
             "finalAmount": 9, "itemInventoryId": 7, "userEmail": usuario})])

    def decidir(self):
        self.fusao.tick(T0 + 10_000)
        return {v.id: v.resultado for v in self.fusao.decididas}

    def unica(self):
        resultados = list(self.decidir().values())
        self.assertEqual(len(resultados), 1)
        return resultados[0]

    def ocorrencias(self):
        return self.banco.listar_ocorrencias()["itens"]


class Cenarios(Base):
    def test_pegou_e_pagou(self):
        self.fusao.adicionar(pessoa(pegadas=[10], totem=[(40, 50)]))
        self.pagar(48)
        r = self.unica()
        self.assertEqual(r["nivel"], "ok")
        self.assertIsNotNone(r["pagamento_id"])
        self.assertEqual(self.ocorrencias(), [])

    def test_pegou_sem_pagar_e_alerta_com_ocorrencia_notificada(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        r = self.unica()
        self.assertEqual(r["nivel"], "alerta")
        self.assertIn("sem_pagamento", sinais(r))
        ocorrencias = self.ocorrencias()
        self.assertEqual([(o["visita_id"], o["situacao"]) for o in ocorrencias], [(r["id"], "aberta")])
        self.assertIn("ocorrencia", [tipo for tipo, _ in self.notificacoes])

    def test_foi_ao_totem_e_nao_pagou_pesa_mais_que_nao_ir_ao_totem(self):
        self.fusao.adicionar(pessoa(pegadas=[10], totem=[(40, 50)]))
        no_totem = self.unica()
        self.fusao.decididas.clear()
        self.fusao.adicionar(pessoa(inicio=1000, fim=1060, pegadas=[1010]))
        longe_do_totem = self.unica()
        self.assertIn("totem_sem_pagamento", sinais(no_totem))
        self.assertGreater(no_totem["score"], longe_do_totem["score"])

    def test_totem_visivel_e_nao_passou_nele_e_alerta(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        r = self.unica()
        self.assertEqual(r["nivel"], "alerta")
        self.assertIn("nao_foi_ao_totem", sinais(r))

    def test_sem_ver_o_totem_so_a_api_decide_e_fica_um_nivel_abaixo(self):
        p = pessoa(camera="bolognalife2b", pegadas=[10])
        p.produto_s, p.ultimo_produto = 5.0, p.fim - 1
        self.fusao.adicionar(p)
        r = self.unica()
        self.assertGreaterEqual(r["score"], self.cfg["fusao"]["niveis"]["alerta"])
        self.assertEqual(r["nivel"], "atencao")
        self.assertIn("so_api", sinais(r))

    def test_sem_ver_o_totem_e_pagou_na_api_fica_ok(self):
        self.fusao.adicionar(pessoa(camera="bolognalife2b", pegadas=[10]))
        self.pagar(58)
        self.assertEqual(self.unica()["nivel"], "ok")

    def test_pagamento_de_outra_loja_nao_conta(self):
        self.fusao.adicionar(pessoa(camera="vguard", pegadas=[10]))
        self.pagar(55, pdv=42)
        r = self.unica()
        self.assertIsNone(r["pagamento_id"])
        self.assertEqual(r["loja"], "vguard")
        self.pagar(56, pdv=77)
        self.fusao.decididas.clear()
        self.fusao.adicionar(pessoa(camera="vguard", inicio=1000, fim=1060, pegadas=[1010]))
        self.pagar(1055, pdv=77)
        self.assertEqual(self.unica()["nivel"], "ok")

    def test_loja_com_dois_totens_aceita_pagamento_em_qualquer_um(self):
        self.cfg["lojas"]["vguard"]["pdv"] = "77, 78"
        self.tp = TouchPay(self.cfg, self.banco)
        self.assertEqual(self.tp.pdvs, [42, 77, 78])
        self.fusao.adicionar(pessoa(camera="vguard", pegadas=[10]))
        self.pagar(55, pdv=78)
        r = self.unica()
        self.assertIsNotNone(r["pagamento_id"])
        self.assertEqual(r["nivel"], "ok")
        self.assertEqual(self.banco.pagamentos_entre(T0, T0 + 100)[0]["loja"], "vguard")

    def test_movimentacao_em_qualquer_totem_da_loja_conta_como_reposicao(self):
        self.cfg["lojas"]["vguard"]["pdv"] = ["77", "78"]
        self.banco.salvar_movimentacoes([self.tp.normalizar_movimentacao(
            {"id": 1, "date": iso(T0 + 40), "type": "Repositioning", "productId": 1, "userEmail": "x@vguard"}, pdv=78)])
        self.assertEqual(len(self.banco.operador_entre(T0, T0 + 100, ["77", "78"])), 1)
        self.assertEqual(self.banco.operador_entre(T0, T0 + 100, ["42"]), [])

    def test_lojas_diferentes_nao_viram_a_mesma_visita(self):
        self.fusao.adicionar(pessoa(camera="bolognalife2", pegadas=[10], roupa=ROUPA_AZUL))
        self.fusao.adicionar(pessoa(camera="vguard", pegadas=[12], roupa=ROUPA_AZUL))
        self.assertEqual(len(self.decidir()), 2)

    def test_loja_sem_pdv_configurado_nao_vira_alerta(self):
        self.cfg["lojas"]["itacolomi"]["pdv"] = ""
        self.cfg["cameras"]["itacolomi"]["cobre_totem"] = True
        self.fusao.adicionar(pessoa(camera="itacolomi", pegadas=[10]))
        r = self.unica()
        self.assertEqual(r["nivel"], "atencao")
        self.assertIn("PDV", r["motivos"][-1]["texto"])

    def test_visita_relampago_nao_vira_alerta(self):
        self.fusao.adicionar(pessoa(inicio=0, fim=3, pegadas=[1]))
        r = self.unica()
        self.assertEqual(r["nivel"], "atencao")
        self.assertIn("provavel_fragmento", sinais(r))

    def test_nao_pegou_nada(self):
        self.fusao.adicionar(pessoa())
        self.assertEqual(self.unica()["nivel"], "ok")

    def test_pagou_pelo_app_sem_ir_ao_totem(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.pagar(55, metodo="AppPix")
        r = self.unica()
        self.assertEqual(r["nivel"], "ok")
        self.assertIn("pagou_pelo_app", sinais(r))

    def test_venda_de_outro_pdv_nao_conta(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.pagar(55, pdv=99)
        self.assertEqual(self.unica()["nivel"], "alerta")

    def test_pagou_menos_itens(self):
        self.fusao.adicionar(pessoa(pegadas=[5, 15, 25, 35], totem=[(40, 50)]))
        self.pagar(48, itens=1)
        r = self.unica()
        self.assertIsNotNone(r["pagamento_id"])
        self.assertIn("itens_a_mais", sinais(r))
        self.assertEqual(r["nivel"], "atencao")

    def test_pagamento_atrasado_resolve_ocorrencia(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        r = self.unica()
        self.assertEqual(r["nivel"], "alerta")
        self.pagar(60 + 200)
        self.fusao.revisar_pagamentos_tardios(T0 + 300)
        ocorrencia = self.ocorrencias()[0]
        self.assertEqual(ocorrencia["situacao"], "resolvida")
        self.assertIsNotNone(self.banco.pagamento_da_visita(r["id"]))
        self.assertEqual(self.banco.listar_visitas()["itens"][0]["nivel"], "ok")

    def test_duas_cameras_mesma_pessoa_uma_visita(self):
        self.fusao.adicionar(pessoa("bolognalife2", 0, 40, pegadas=[10], roupa=ROUPA_AZUL))
        self.fusao.adicionar(pessoa("bolognalife2b", 30, 70, pegadas=[10.5], roupa=ROUPA_AZUL))
        r = self.unica()
        self.assertEqual(r["cameras"], ["bolognalife2", "bolognalife2b"])
        self.assertEqual(r["pegadas"], 1)

    def test_duas_pessoas_roupas_diferentes_ao_mesmo_tempo(self):
        self.fusao.adicionar(pessoa("bolognalife2", 0, 60, roupa=ROUPA_AZUL, ident="a1"))
        self.fusao.adicionar(pessoa("bolognalife2", 100, 160, roupa=ROUPA_AZUL, ident="a2"))
        self.fusao.adicionar(pessoa("bolognalife2b", 5, 65, roupa=ROUPA_AZUL, ident="b1"))
        self.fusao.adicionar(pessoa("bolognalife2b", 10, 70, roupa=ROUPA_VERMELHA, ident="b2"))
        self.assertEqual(len(self.decidir()), 3)

    def test_grupo_um_paga_pelos_dois(self):
        self.fusao.adicionar(pessoa("bolognalife2", 0, 90, pegadas=[10], totem=[(70, 80)], roupa=ROUPA_AZUL, ident="a"))
        self.fusao.adicionar(pessoa("bolognalife2", 5, 92, pegadas=[20], roupa=ROUPA_VERMELHA, ident="b"))
        self.pagar(78)
        niveis = sorted(r["nivel"] for r in self.decidir().values())
        self.assertEqual(niveis, ["ok", "ok"])

    def test_pagamento_vai_para_quem_estava_no_totem(self):
        self.fusao.adicionar(pessoa("bolognalife2", 0, 50, pegadas=[10], roupa=ROUPA_AZUL, ident="a"))
        self.fusao.adicionar(pessoa("bolognalife2", 30, 120, pegadas=[60], totem=[(95, 105)], roupa=ROUPA_VERMELHA, ident="b"))
        self.pagar(104)
        por_parte = {r["partes"][0]["id"]: r for r in self.decidir().values()}
        self.assertIsNone(por_parte["a"]["pagamento_id"])
        self.assertIsNotNone(por_parte["b"]["pagamento_id"])

    def test_pagamento_preso_em_visita_sem_produto_vai_para_quem_pegou(self):
        self.fusao.adicionar(pessoa("bolognalife2", 50, 100, totem=[(90, 100)], roupa=ROUPA_AZUL, ident="a"))
        self.fusao.adicionar(pessoa("bolognalife2", 85, 160, pegadas=[120], roupa=ROUPA_VERMELHA, ident="b"))
        self.pagar(98)
        self.fusao.tick(T0 + 225)
        self.assertIsNotNone(self.banco.pagamento_da_visita(self.fusao.decididas[0].id))
        por_parte = {r["partes"][0]["id"]: r for r in self.decidir().values()}
        self.assertEqual(por_parte["b"]["nivel"], "ok")
        self.assertIsNotNone(por_parte["b"]["pagamento_id"])
        self.assertIsNone(self.banco.pagamento_da_visita(por_parte["a"]["id"]))

    def test_acompanhante_com_pagamento_tardio_resolve_a_ocorrencia_do_grupo(self):
        self.fusao.adicionar(pessoa("bolognalife2", 0, 30, pegadas=[10], roupa=ROUPA_AZUL, ident="a"))
        self.fusao.adicionar(pessoa("bolognalife2", 5, 90, pegadas=[20], roupa=ROUPA_VERMELHA, ident="b"))
        self.assertEqual(sorted(r["nivel"] for r in self.decidir().values()), ["alerta", "alerta"])
        self.pagar(300)
        self.fusao.revisar_pagamentos_tardios(T0 + 400)
        self.fusao.revisar_pagamentos_tardios(T0 + 401)
        self.assertEqual({o["situacao"] for o in self.ocorrencias()}, {"resolvida"})

    def test_revisao_de_tardios_roda_pelo_tick_no_intervalo(self):
        self.fusao._ultima_revisao = 0.0
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.fusao.tick(T0 + 200)
        self.assertEqual(self.ocorrencias()[0]["situacao"], "aberta")
        self.pagar(195)
        self.fusao.tick(T0 + 210)
        self.assertEqual(self.ocorrencias()[0]["situacao"], "aberta")
        self.fusao.tick(T0 + 200 + 31)
        self.assertEqual(self.ocorrencias()[0]["situacao"], "resolvida")

    def test_produto_na_mao_por_pouco_tempo_vira_atencao(self):
        self.cfg["fusao"]["pesos"]["pegada_fraca"] = -20
        p = pessoa(pegadas=[10])
        p.produto_s = 0.5
        self.fusao.adicionar(p)
        r = self.unica()
        self.assertEqual(r["nivel"], "atencao")
        self.assertIn("pegada_fraca", sinais(r))

    def test_sumiu_com_produto_na_mao_pesa_mais(self):
        p = pessoa(camera="bolognalife2b", pegadas=[10])
        p.produto_s, p.ultimo_produto = 5.0, p.fim - 1
        self.fusao.adicionar(p)
        r = self.unica()
        self.assertIn("saiu_com_produto", sinais(r))
        self.assertEqual(r["nivel"], "atencao")

    def test_entrou_com_objeto_proprio_alivia(self):
        p = pessoa(pegadas=[10])
        p.objetos_proprios = [ROUPA_AZUL]
        self.fusao.adicionar(p)
        r = self.unica()
        self.assertIn("entrou_com_objeto", sinais(r))
        self.assertEqual(r["nivel"], "atencao")

    def test_reposicao_pela_movimentacao_de_estoque(self):
        self.fusao.adicionar(pessoa(pegadas=[10, 20, 30]))
        self.operador(40)
        r = self.unica()
        self.assertEqual(r["nivel"], "reposicao")
        self.assertIn("repositor@loja", r["motivos"][0]["texto"])
        self.assertEqual(self.ocorrencias(), [])

    def test_reposicao_por_horario_configurado(self):
        local = datetime.fromtimestamp(T0, self.fusao.fuso)
        self.cfg["fusao"]["reposicao"]["horarios"] = [f"{local:%H:%M}-{local.hour:02d}:59"]
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.assertEqual(self.unica()["nivel"], "reposicao")

    def test_movimentacao_de_outra_loja_nao_e_reposicao(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.banco.salvar_movimentacoes([self.tp.normalizar_movimentacao(
            {"id": 1, "date": iso(T0 + 40), "type": "Repositioning", "productId": 1, "userEmail": "x@vguard"}, pdv=77)])
        self.assertEqual(self.unica()["nivel"], "alerta")

    def test_movimentacao_que_chega_depois_resolve_ocorrencia(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.assertEqual(self.unica()["nivel"], "alerta")
        self.operador(50)
        self.fusao.revisar_pagamentos_tardios(T0 + 300)
        ocorrencia = self.ocorrencias()[0]
        self.assertEqual(ocorrencia["situacao"], "resolvida")
        self.assertIn("repositor@loja", ocorrencia["resolucao"])
        self.assertEqual(self.banco.listar_visitas()["itens"][0]["nivel"], "reposicao")

    def test_venda_automatica_no_estoque_nao_e_reposicao(self):
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.operador(40, tipo="Sale", usuario=None)
        self.assertEqual(self.unica()["nivel"], "alerta")


class TouchPayEntrada(Base):
    def test_normaliza_transacao_sem_dados_pessoais(self):
        p = self.tp.normalizar(venda(10, itens=3, metodo="AppSale"))
        self.assertEqual((p["situacao"], p["qtd_itens"], p["metodo"], p["valor"]), ("aprovado", 3, "AppSale", 9.5))
        self.assertAlmostEqual(p["horario"], T0 + 10)
        self.assertEqual(p["loja"], "bologna")
        self.assertNotIn("userInfo", p)
        self.assertNotIn("cliente", p)
        serializado = json.dumps(p)
        for dado_pessoal in ("123.456.789-00", "12345678900", "x@y.com", "11999999999"):
            self.assertNotIn(dado_pessoal, serializado)

    def test_registrar_lista_e_ignora_lixo(self):
        self.assertEqual(self.tp.registrar([venda(6, ident="a"), venda(7, ident="b"), "lixo", {"sem": "uuid"}]), 2)
        self.assertEqual(self.tp.registrar([venda(6, ident="a")]), 1)
        self.assertEqual(len(self.banco.pagamentos_entre(T0, T0 + 100)), 2)
        self.assertEqual(self.tp.recebidos, 3)

    def test_data_sem_fuso_usa_fuso_da_api(self):
        p = self.tp.normalizar({**venda(0), "date": "2026-11-05T10:00:00"})
        self.assertEqual(datetime.fromtimestamp(p["horario"], timezone.utc).hour, 13)

    def test_movimentacao_classifica_operacao_humana_e_contagem(self):
        humana = self.tp.normalizar_movimentacao({"id": 1, "date": iso(T0), "type": "Correction", "productId": 5,
                                                  "changeAmount": -3}, pdv=42)
        automatica = self.tp.normalizar_movimentacao({"id": 2, "date": iso(T0), "type": "Sale"})
        self.assertEqual((humana["humana"], humana["contagem"], humana["pdv"], humana["quantidade"]), (True, True, "42", -3))
        self.assertEqual((automatica["humana"], automatica["contagem"], automatica["pdv"]), (False, False, None))


class TouchPayFalsa(BaseHTTPRequestHandler):
    pedidos = []

    def responder(self, codigo, corpo):
        dados = json.dumps(corpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ok = corpo == {"email": "central@loja", "password": "s3nha"}
        self.responder(200 if ok else 401, {"token": "novo-token"} if ok else {})

    def do_GET(self):
        TouchPayFalsa.pedidos.append((self.path, self.headers.get("Authorization")))
        if self.headers.get("Authorization") != "Bearer novo-token":
            return self.responder(401, {})
        if self.path.startswith("/api/public/pointsOfSale"):
            return self.responder(200, [{"id": 42, "inventoryId": 7}, {"id": 99, "inventoryId": 8}])
        pagina = int(self.path.split("Page=")[1].split("&")[0])
        if self.path.startswith("/api/public/inventory/transactions"):
            return self.responder(200, {"items": [{"id": 500 + pagina, "date": iso(T0), "type": "Repositioning",
                                                   "userEmail": "r@loja"}], "hasNextPage": False})
        itens = [venda(pagina * 10 + i, ident=f"v-{pagina}-{i}") for i in range(2)]
        self.responder(200, {"items": itens, "hasNextPage": pagina < 3})

    def log_message(self, *_):
        pass


class TouchPayPolling(Base):
    def setUp(self):
        super().setUp()
        TouchPayFalsa.pedidos.clear()
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), TouchPayFalsa)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.cfg["touchpay"]["url"] = f"http://127.0.0.1:{self.servidor.server_port}"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        super().tearDown()

    def test_varios_pdvs_le_sem_filtro_e_descarta_lojas_de_fora(self):
        self.cfg["touchpay"]["autenticacao"] = {"token": "novo-token"}
        tp = TouchPay(self.cfg, self.banco)
        self.assertEqual(tp.pdvs, [42, 77])
        tp.consultar_vendas(agora=T0 + 100)
        self.assertNotIn("PointOfSaleId", TouchPayFalsa.pedidos[-1][0])
        self.assertIsNone(tp.normalizar(venda(1, pdv=99)))
        self.assertIsNotNone(tp.normalizar(venda(1, pdv=77)))

    def test_login_quando_token_expira_e_paginacao(self):
        self.cfg["lojas"]["vguard"]["pdv"] = ""
        self.cfg["touchpay"]["autenticacao"] = {"token": "token-vencido", "email": "central@loja", "senha": "s3nha",
                                                "login_caminho": "/login", "campo_token": "token"}
        tp = TouchPay(self.cfg, self.banco)
        self.assertEqual(tp.consultar_vendas(agora=T0 + 100), 6)
        self.assertIn("PointOfSaleId=42", TouchPayFalsa.pedidos[0][0])
        self.assertEqual(TouchPayFalsa.pedidos[0][1], "Bearer token-vencido")
        self.assertEqual(TouchPayFalsa.pedidos[-1][1], "Bearer novo-token")
        self.assertEqual(len(self.banco.pagamentos_entre(T0, T0 + 100)), 6)
        self.assertEqual(tp.ultima_consulta, T0 + 100)

    def test_estoque_descobre_inventario_so_dos_pdvs_configurados(self):
        self.cfg["touchpay"]["autenticacao"] = {"token": "novo-token"}
        tp = TouchPay(self.cfg, self.banco)
        self.assertEqual(tp.consultar_estoque(agora=T0 + 100), 1)
        self.assertEqual(tp.inventarios, {42: 7})
        consulta = next(caminho for caminho, _ in TouchPayFalsa.pedidos if "inventory/transactions" in caminho)
        self.assertIn("InventoryId=7", consulta)
        self.assertEqual([m["pdv"] for m in self.banco.operador_entre(T0 - 1, T0 + 1)], ["42"])

    def test_sem_url_nao_cria_cliente(self):
        self.cfg["touchpay"]["url"] = ""
        tp = TouchPay(self.cfg, self.banco)
        self.assertIsNone(tp.cliente)
        self.assertFalse(tp.status()["configurado"])


class ProdutoNaMao(unittest.TestCase):
    VERMELHO, AZUL = (100, 100, 150, 150), (300, 300, 350, 350)

    def setUp(self):
        self.cam = CameraAnalise.__new__(CameraAnalise)
        self.cam.p = {"produto_intervalo_s": 8.0, "produto_janela_s": 2.0, "produto_min_deteccoes": 2,
                      "mao_vazia_antes_s": 4.0, "mesmo_objeto": 0.7}
        self.cam.eventos = []
        self.cam._registrar_evento = lambda t, pessoa, tipo, texto: self.cam.eventos.append(tipo)
        self.cam._foto = lambda *a, **k: "foto.jpg"
        self.cam._momento = False
        self.frame = np.zeros((480, 640, 3), np.uint8)
        self.frame[100:150, 100:150] = (0, 0, 255)
        self.frame[300:350, 300:350] = (255, 0, 0)
        self.p = PessoaCamera("c", "c-1", 0, 0)

    def ver(self, de, ate, caixa=None, passo=0.2):
        t = de
        while t < ate:
            CameraAnalise._produto_na_mao(self.cam, self.p, self.frame, t, passo, caixa)
            self.p.fim = t
            t += passo

    def test_entrou_ja_com_objeto_nao_conta(self):
        self.ver(0, 20, self.VERMELHO)
        self.assertEqual(self.p.pegadas, [])
        self.assertIn("objeto", self.cam.eventos)

    def test_mao_vazia_e_depois_produto_conta(self):
        self.ver(0, 6)
        self.ver(6, 10, self.AZUL)
        self.assertEqual(len(self.p.pegadas), 1)
        self.assertGreater(self.p.produto_s, 2)
        self.assertTrue(self.p.saiu_com_produto)
        self.assertIn("pegou", self.cam.eventos)

    def test_objeto_trazido_que_some_e_volta_nao_conta(self):
        self.ver(0, 3, self.VERMELHO)
        self.ver(3, 15)
        self.ver(15, 18, self.VERMELHO)
        self.assertEqual(self.p.pegadas, [])

    def test_objeto_trazido_e_depois_produto_diferente_conta(self):
        self.ver(0, 3, self.VERMELHO)
        self.ver(3, 15)
        self.ver(15, 18, self.AZUL)
        self.assertEqual(len(self.p.pegadas), 1)

    def test_deteccao_relampago_nao_zera_a_mao_vazia(self):
        self.ver(0, 6)
        self.ver(6, 6.2, self.VERMELHO)
        self.ver(6.2, 7)
        self.ver(7, 10, self.AZUL)
        self.assertEqual(len(self.p.pegadas), 1)

    def test_deteccao_relampago_nao_conta(self):
        self.ver(0, 6)
        self.ver(6, 6.1, self.AZUL)
        self.ver(6.3, 12)
        self.assertEqual(self.p.pegadas, [])


if __name__ == "__main__":
    unittest.main()
