import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic
import cv2
import httpx
import numpy as np
import openai

from vigia.config import carregar
from vigia.fusao import Fusao
from vigia.triagem import BETA_FALLBACK, ESQUEMA_PARECER, Triagem

from apoio import banco_de_teste
from test_fusao import T0, pessoa, configuracao_isolada as configuracao_da_fusao

CAMERA = "bolognalife2"


def resposta(veredito="furto_provavel", confianca=85, resumo="Pega um refrigerante e sai sem passar no totem.",
             stop_reason="end_turn", texto=None):
    corpo = texto if texto is not None else json.dumps(
        {"veredito": veredito, "confianca": confianca, "resumo": resumo, "sinais": ["mão com lata", "não vai ao totem"],
         "justificativa": "No quadro 3 da bolognalife2 a lata está na mão e não há venda perto."})
    return SimpleNamespace(stop_reason=stop_reason, model="claude-opus-5-5", content=[SimpleNamespace(type="text", text=corpo)])


def erro_de_conexao():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


class ClienteFalso:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._criar))

    def _criar(self, **parametros):
        self.chamadas.append(parametros)
        proxima = self.respostas.pop(0)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


def resposta_openai(veredito="furto_provavel", confianca=85, resumo="Pega um refrigerante e sai sem passar no totem.",
                    finish_reason="stop", texto=None, recusa=None):
    corpo = texto if texto is not None else json.dumps(
        {"veredito": veredito, "confianca": confianca, "resumo": resumo, "sinais": ["mão com lata", "não vai ao totem"],
         "justificativa": "No quadro 3 da bolognalife2 a lata está na mão e não há venda perto."})
    mensagem = SimpleNamespace(content=corpo, refusal=recusa)
    return SimpleNamespace(model="gpt-5.5-2026-04-23", choices=[SimpleNamespace(message=mensagem, finish_reason=finish_reason)])


def erro_de_conexao_openai():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))


class ClienteOpenAIFalso(ClienteFalso):
    def __init__(self, *respostas):
        super().__init__(*respostas)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._criar))


class BaseTriagem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = configuracao_da_fusao(self.tmp.name)
        self.cfg["triagem_ia"]["ativa"] = True
        self.cfg["triagem_ia"]["provedor"] = "anthropic"
        self.cfg["triagem_ia"]["modelo"] = "claude-opus-5-5"
        self.banco = banco_de_teste()
        self.notificacoes = []
        self.raiz = Path(self.cfg["dados"]["evidencias"])

    def tearDown(self):
        self.banco.fechar()
        self.tmp.cleanup()

    def notificar(self, tipo, dados):
        self.notificacoes.append((tipo, dados))

    def tipos_notificados(self):
        return [tipo for tipo, _ in self.notificacoes]

    def triagem(self, cliente):
        return Triagem(self.cfg, self.banco, self.notificar, cliente)

    def foto(self, nome="p1_pegou1.jpg"):
        caminho = self.raiz / CAMERA / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(caminho), np.full((720, 1280, 3), 128, np.uint8))
        return f"{CAMERA}/{nome}"

    def nova_ocorrencia(self, evidencias=None, nivel="alerta"):
        agora = time.time()
        visita = {"id": f"v{len(self.banco.listar_ocorrencias()['itens']) + 1}", "loja": "bologna", "inicio": agora - 60,
                  "fim": agora, "cameras": [CAMERA], "pegadas": 1, "foi_totem": False, "score": 75, "nivel": nivel,
                  "pagamento_id": None, "motivos": [{"sinal": "sem_pagamento", "peso": 60, "texto": "pegou 1x e não há pagamento"}],
                  "grupo": [], "partes": [{"camera": CAMERA, "id": "p1", "inicio": agora - 60, "fim": agora,
                                           "pegadas": [agora - 30], "totem": [], "saiu_com_produto": True}]}
        self.banco.salvar_visita(visita)
        fotos = [self.foto()] if evidencias is None else evidencias
        return self.banco.criar_ocorrencia(visita, fotos, "triagem")

    def depois_da_espera(self):
        return time.time() + self.cfg["triagem_ia"]["espera_clipe_s"] + 1


class Decisao(BaseTriagem):
    def test_falso_positivo_com_confianca_alta_sai_da_fila_humana(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta("falso_positivo", 92, "É o celular do cliente."))).processar_pendentes(self.depois_da_espera())
        ocorrencia = self.banco.ocorrencia(ocorrencia_id)
        self.assertEqual(ocorrencia["situacao"], "descartada")
        self.assertEqual(ocorrencia["ia"]["veredito"], "falso_positivo")
        self.assertEqual(ocorrencia["ia"]["situacao"], "concluida")
        self.assertEqual(self.tipos_notificados(), ["ocorrencia_descartada"])
        self.assertEqual(self.banco.contar_ocorrencias_abertas(), 0)

    def test_furto_provavel_vai_para_o_operador_com_o_resumo_da_ia(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta())).processar_pendentes(self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "aberta")
        tipo, aviso = self.notificacoes[0]
        self.assertEqual(tipo, "ocorrencia")
        self.assertEqual(aviso["id"], ocorrencia_id)
        self.assertTrue(aviso["motivo"].startswith("IA: Pega um refrigerante"))
        self.assertEqual(aviso["evidencia"], f"{CAMERA}/p1_pegou1.jpg")

    def test_falso_positivo_com_pouca_confianca_continua_com_o_operador(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta("falso_positivo", 60))).processar_pendentes(self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "aberta")
        self.assertEqual(self.tipos_notificados(), ["ocorrencia"])

    def test_descarte_desligado_no_config_manda_tudo_para_o_operador(self):
        self.cfg["triagem_ia"]["descartar_falso_positivo"] = False
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta("falso_positivo", 99))).processar_pendentes(self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "aberta")

    def test_inconclusivo_vai_para_o_operador(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta("inconclusivo", 40))).processar_pendentes(self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "aberta")

    def test_confianca_fora_da_faixa_e_limitada(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta("furto_provavel", 140))).processar_pendentes(self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["ia"]["confianca"], 100)

    def test_ocorrencia_resolvida_durante_a_triagem_continua_resolvida(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.banco.resolver_ocorrencia("v1", None, "pagamento chegou depois da decisão", "ok")
        triagem = self.triagem(ClienteFalso(resposta()))
        triagem.triar(self.banco.ocorrencia(ocorrencia_id), self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "resolvida")
        self.assertEqual(self.notificacoes, [])


class Fila(BaseTriagem):
    def test_espera_o_clipe_antes_de_analisar(self):
        self.nova_ocorrencia()
        cliente = ClienteFalso(resposta())
        self.triagem(cliente).processar_pendentes(time.time())
        self.assertEqual(cliente.chamadas, [])

    def test_clipe_pronto_libera_a_analise_antes_da_espera(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.banco.adicionar_clipe(ocorrencia_id, f"clipes/ocorrencia{ocorrencia_id}_{CAMERA}.mp4")
        cliente = ClienteFalso(resposta())
        self.triagem(cliente).processar_pendentes(time.time())
        self.assertEqual(len(cliente.chamadas), 1)

    def test_frames_do_clipe_entram_na_analise(self):
        ocorrencia_id = self.nova_ocorrencia()
        clipe = self.raiz / "clipes" / f"ocorrencia{ocorrencia_id}_{CAMERA}.mp4"
        clipe.parent.mkdir(parents=True, exist_ok=True)
        gravador = cv2.VideoWriter(str(clipe), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
        for indice in range(40):
            gravador.write(np.full((240, 320, 3), indice * 5, np.uint8))
        gravador.release()
        self.banco.adicionar_clipe(ocorrencia_id, str(clipe.relative_to(self.raiz)))
        cliente = ClienteFalso(resposta())
        self.triagem(cliente).processar_pendentes(time.time())
        conteudo = cliente.chamadas[0]["messages"][0]["content"]
        imagens = [b for b in conteudo if b["type"] == "image"]
        self.assertEqual(len(imagens), 1 + self.cfg["triagem_ia"]["quadros_por_clipe"])
        self.assertTrue(any(b["type"] == "text" and b["text"].startswith(f"Vídeo da câmera {CAMERA}, quadro 1") for b in conteudo))
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["ia"]["imagens"], len(imagens))

    def test_erro_da_api_tenta_de_novo_e_depois_manda_para_o_operador(self):
        ocorrencia_id = self.nova_ocorrencia()
        cliente = ClienteFalso(erro_de_conexao(), erro_de_conexao(), erro_de_conexao())
        triagem = self.triagem(cliente)
        agora = self.depois_da_espera()
        intervalo = self.cfg["triagem_ia"]["intervalo_tentativas_s"]
        triagem.processar_pendentes(agora)
        triagem.processar_pendentes(agora + 1)
        self.assertEqual(len(cliente.chamadas), 1)
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "triagem")
        triagem.processar_pendentes(agora + intervalo + 1)
        triagem.processar_pendentes(agora + 2 * intervalo + 2)
        ocorrencia = self.banco.ocorrencia(ocorrencia_id)
        self.assertEqual(len(cliente.chamadas), 3)
        self.assertEqual(ocorrencia["situacao"], "aberta")
        self.assertEqual(ocorrencia["ia"]["situacao"], "erro")
        self.assertEqual(self.tipos_notificados(), ["ocorrencia"])
        self.assertEqual(triagem.status()["erros"], 3)

    def test_recusa_da_ia_conta_como_erro(self):
        self.cfg["triagem_ia"]["tentativas"] = 1
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta(stop_reason="refusal", texto=""))).processar_pendentes(self.depois_da_espera())
        ocorrencia = self.banco.ocorrencia(ocorrencia_id)
        self.assertEqual((ocorrencia["situacao"], ocorrencia["ia"]["situacao"]), ("aberta", "erro"))
        self.assertIn("recusou", ocorrencia["ia"]["erro"])

    def test_resposta_fora_do_formato_conta_como_erro(self):
        self.cfg["triagem_ia"]["tentativas"] = 1
        ocorrencia_id = self.nova_ocorrencia()
        self.triagem(ClienteFalso(resposta(texto='{"veredito": "talvez"}'))).processar_pendentes(self.depois_da_espera())
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["ia"]["situacao"], "erro")

    def test_sem_imagens_vai_direto_para_o_operador(self):
        ocorrencia_id = self.nova_ocorrencia(evidencias=[])
        cliente = ClienteFalso()
        self.triagem(cliente).processar_pendentes(self.depois_da_espera())
        ocorrencia = self.banco.ocorrencia(ocorrencia_id)
        self.assertEqual(cliente.chamadas, [])
        self.assertEqual((ocorrencia["situacao"], ocorrencia["ia"]["situacao"]), ("aberta", "sem_imagens"))

    def test_triagem_desligada_libera_o_que_ficou_na_fila(self):
        ocorrencia_id = self.nova_ocorrencia()
        self.cfg["triagem_ia"]["ativa"] = False
        Triagem(self.cfg, self.banco, self.notificar).iniciar()
        ocorrencia = self.banco.ocorrencia(ocorrencia_id)
        self.assertEqual((ocorrencia["situacao"], ocorrencia["ia"]["situacao"]), ("aberta", "desligada"))

    def test_sem_chave_da_api_a_triagem_fica_desligada(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertFalse(Triagem(self.cfg, self.banco, self.notificar).ativa)

    def test_provedor_desconhecido_deixa_a_triagem_desligada(self):
        self.cfg["triagem_ia"]["provedor"] = "outro"
        self.assertFalse(Triagem(self.cfg, self.banco, self.notificar).ativa)


class TriagemOpenAI(BaseTriagem):
    def setUp(self):
        super().setUp()
        self.cfg["triagem_ia"]["provedor"] = "openai"
        self.cfg["triagem_ia"]["modelo"] = "gpt-5.5"

    def chamada(self, *respostas):
        ocorrencia_id = self.nova_ocorrencia()
        cliente = ClienteOpenAIFalso(*(respostas or [resposta_openai()]))
        self.triagem(cliente).processar_pendentes(self.depois_da_espera())
        return ocorrencia_id, cliente

    def test_config_padrao_usa_openai(self):
        self.assertEqual(carregar(ambiente="dev")["triagem_ia"]["provedor"], "openai")

    def test_pede_json_estrito_com_fotos_em_data_url(self):
        _, cliente = self.chamada()
        chamada = cliente.chamadas[0]
        self.assertEqual(chamada["model"], "gpt-5.5")
        self.assertEqual(chamada["reasoning_effort"], "medium")
        self.assertEqual(chamada["response_format"]["type"], "json_schema")
        self.assertTrue(chamada["response_format"]["json_schema"]["strict"])
        self.assertEqual(chamada["messages"][0]["role"], "system")
        conteudo = chamada["messages"][1]["content"]
        imagem = next(b for b in conteudo if b["type"] == "image_url")
        self.assertTrue(imagem["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertIn("Bologna Life", conteudo[-1]["text"])

    def test_parecer_da_openai_decide_a_ocorrencia(self):
        ocorrencia_id, _ = self.chamada(resposta_openai("falso_positivo", 95, "É a carteira do cliente."))
        ocorrencia = self.banco.ocorrencia(ocorrencia_id)
        self.assertIn("quadro 3", ocorrencia["ia"]["justificativa"])
        self.assertIn("justificativa", ESQUEMA_PARECER["required"])
        self.assertEqual(ocorrencia["situacao"], "descartada")
        self.assertEqual((ocorrencia["ia"]["modelo"], ocorrencia["ia"]["imagens"]), ("gpt-5.5-2026-04-23", 1))

    def test_sem_esforco_nao_manda_reasoning_effort(self):
        self.cfg["triagem_ia"]["esforco"] = ""
        _, cliente = self.chamada()
        self.assertNotIn("reasoning_effort", cliente.chamadas[0])

    def test_recusa_e_resposta_cortada_contam_como_erro(self):
        self.cfg["triagem_ia"]["tentativas"] = 1
        for resposta_ruim, trecho in ((resposta_openai(texto=None, recusa="não posso ajudar"), "recusou"),
                                      (resposta_openai(finish_reason="length"), "cortada")):
            ocorrencia_id, _ = self.chamada(resposta_ruim)
            ocorrencia = self.banco.ocorrencia(ocorrencia_id)
            self.assertEqual((ocorrencia["situacao"], ocorrencia["ia"]["situacao"]), ("aberta", "erro"))
            self.assertIn(trecho, ocorrencia["ia"]["erro"])

    def test_erro_da_api_da_openai_tenta_de_novo(self):
        ocorrencia_id, cliente = self.chamada(erro_de_conexao_openai())
        self.assertEqual(len(cliente.chamadas), 1)
        self.assertEqual(self.banco.ocorrencia(ocorrencia_id)["situacao"], "triagem")

    def test_sem_chave_da_openai_a_triagem_fica_desligada(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertFalse(Triagem(self.cfg, self.banco, self.notificar).ativa)


class Requisicao(BaseTriagem):
    def chamada(self):
        self.nova_ocorrencia()
        cliente = ClienteFalso(resposta())
        self.triagem(cliente).processar_pendentes(self.depois_da_espera())
        return cliente.chamadas[0]

    def test_pede_resposta_estruturada_com_fallback_e_esforco_do_config(self):
        chamada = self.chamada()
        self.assertEqual(chamada["model"], "claude-opus-5-5")
        self.assertEqual(chamada["betas"], [BETA_FALLBACK])
        self.assertEqual(chamada["fallbacks"], "default")
        self.assertEqual(chamada["output_config"]["effort"], "medium")
        self.assertEqual(chamada["output_config"]["format"]["type"], "json_schema")

    def test_manda_fotos_reduzidas_e_os_dados_do_detector(self):
        conteudo = self.chamada()["messages"][0]["content"]
        imagem = next(b for b in conteudo if b["type"] == "image")
        self.assertEqual(imagem["source"]["media_type"], "image/jpeg")
        self.assertIn("produto na mão (1º item)", conteudo[0]["text"])
        contexto = conteudo[-1]["text"]
        self.assertIn("Bologna Life", contexto)
        self.assertIn("pegou 1x e não há pagamento", contexto)
        self.assertIn("saiu com o produto na mão", contexto)

    def test_haiku_nao_recebe_fallback(self):
        self.cfg["triagem_ia"]["modelo"] = "claude-haiku-5-5"
        chamada = self.chamada()
        self.assertNotIn("fallbacks", chamada)
        self.assertNotIn("betas", chamada)


class Integracao(BaseTriagem):
    def setUp(self):
        super().setUp()
        self.cfg["triagem_ia"]["score_acima_de"] = 0

    def fusao(self, triagem):
        fusao = Fusao(self.cfg, self.banco, notificar=self.notificar, triagem=triagem)
        fusao._ultima_revisao = float("inf")
        return fusao

    def test_ocorrencia_nova_espera_a_ia_sem_avisar_o_operador(self):
        fusao = self.fusao(self.triagem(ClienteFalso()))
        fusao.adicionar(pessoa(pegadas=[10]))
        fusao.tick(T0 + 10_000)
        ocorrencia = self.banco.listar_ocorrencias()["itens"][0]
        self.assertEqual(ocorrencia["situacao"], "triagem")
        self.assertEqual(self.tipos_notificados(), ["visita", "ocorrencia_triagem"])

    def test_score_ate_o_limite_vai_direto_para_o_operador(self):
        fusao = self.fusao(self.triagem(ClienteFalso()))
        fusao.adicionar(pessoa(pegadas=[10]))
        fusao.tick(T0 + 10_000)
        score = self.banco.listar_ocorrencias()["itens"][0]["score"]
        self.cfg["triagem_ia"]["score_acima_de"] = score
        fusao = self.fusao(self.triagem(ClienteFalso()))
        fusao.adicionar(pessoa(inicio=20_000, fim=20_060, pegadas=[20_010]))
        fusao.tick(T0 + 30_000)
        mais_nova = self.banco.listar_ocorrencias()["itens"][0]
        self.assertEqual(mais_nova["score"], score)
        self.assertEqual(mais_nova["situacao"], "aberta")
        self.assertEqual(self.tipos_notificados()[-1], "ocorrencia")

    def test_limite_de_score_do_config_e_80(self):
        triagem = self.triagem(ClienteFalso())
        triagem.p["score_acima_de"] = carregar(ambiente="dev")["triagem_ia"]["score_acima_de"]
        self.assertEqual(triagem.p["score_acima_de"], 80)
        self.assertFalse(triagem.aceita({"score": 80}))
        self.assertTrue(triagem.aceita({"score": 81}))

    def test_sem_triagem_a_ocorrencia_abre_direto(self):
        fusao = self.fusao(None)
        fusao.adicionar(pessoa(pegadas=[10]))
        fusao.tick(T0 + 10_000)
        self.assertEqual(self.banco.listar_ocorrencias()["itens"][0]["situacao"], "aberta")
        self.assertIn("ocorrencia", self.tipos_notificados())

    def test_pagamento_tardio_resolve_ocorrencia_em_triagem(self):
        from test_fusao import venda
        from vigia.touchpay import TouchPay

        fusao = self.fusao(self.triagem(ClienteFalso()))
        fusao.adicionar(pessoa(pegadas=[10]))
        fusao.tick(T0 + 10_000)
        TouchPay(self.cfg, self.banco).registrar([venda(60 + 200)])
        fusao.revisar_pagamentos_tardios(T0 + 300)
        self.assertEqual(self.banco.listar_ocorrencias()["itens"][0]["situacao"], "resolvida")


if __name__ == "__main__":
    unittest.main()
