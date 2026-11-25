import os
import time
import unittest
from datetime import datetime, timezone

from test_api import CadastroDeCameras
from test_fusao import T0, Base, configuracao_isolada, pessoa
from vigia.config import aplicar_cadastros, aplicar_loja_cadastrada, recorte_sem_compra
from vigia.retencao import Retencao

ESPERA_DA_LOJA_S = 600


class EvidenciasAnotadas:
    def __init__(self):
        self.pedidos = []

    def pedir_clipes(self, ocorrencia_id, visita, todas_da_loja=False):
        self.pedidos.append((ocorrencia_id, visita.cameras, todas_da_loja))


class TriagemQueAceitaTudo:
    def aceita(self, resultado):
        return True


class EntradaSemCompra(Base):
    def ligar(self, loja="bologna", espera_s=ESPERA_DA_LOJA_S):
        self.cfg["lojas"][loja]["recorte_sem_compra"] = {"ativo": True, "espera_s": espera_s}

    def test_loja_desligada_nao_recorta_quem_so_entrou(self):
        self.fusao.adicionar(pessoa())
        self.assertEqual(self.unica()["nivel"], "ok")
        self.assertEqual(self.ocorrencias(), [])

    def test_loja_ligada_recorta_quem_entrou_e_saiu_sem_comprar(self):
        self.ligar()
        self.fusao.adicionar(pessoa())
        self.decidir()
        [ocorrencia] = self.ocorrencias()
        self.assertEqual((ocorrencia["tipo"], ocorrencia["situacao"], ocorrencia["score"]), ("sem_compra", "aberta", 0))
        self.assertEqual(ocorrencia["motivos"][0]["sinal"], "entrou_sem_comprar")
        self.assertIn("não foi visto pegando produto", ocorrencia["motivos"][1]["texto"])

    def test_pede_o_recorte_de_todas_as_cameras_da_loja(self):
        self.ligar()
        self.fusao.evidencias = EvidenciasAnotadas()
        self.fusao.adicionar(pessoa())
        self.decidir()
        [ocorrencia] = self.ocorrencias()
        self.assertEqual(self.fusao.evidencias.pedidos, [(ocorrencia["id"], ["bolognalife2"], True)])

    def test_espera_o_tempo_da_loja_antes_de_decidir(self):
        self.ligar()
        self.fusao.adicionar(pessoa(fim=60))
        self.fusao.tick(T0 + 60 + ESPERA_DA_LOJA_S - 1)
        self.assertEqual(len(self.fusao.pendentes), 1)
        self.fusao.tick(T0 + 60 + ESPERA_DA_LOJA_S)
        self.assertEqual(len(self.fusao.pendentes), 0)

    def test_compra_dentro_da_espera_nao_gera_ocorrencia(self):
        self.ligar()
        self.fusao.adicionar(pessoa(fim=60))
        self.pagar(60 + ESPERA_DA_LOJA_S - 30)
        self.assertIsNotNone(self.unica()["pagamento_id"])
        self.assertEqual(self.ocorrencias(), [])

    def test_quem_pegou_sem_pagar_continua_como_suspeita(self):
        self.ligar()
        self.fusao.adicionar(pessoa(pegadas=[10]))
        self.decidir()
        self.assertEqual([o["tipo"] for o in self.ocorrencias()], ["suspeita"])

    def test_reposicao_nao_vira_entrada_sem_compra(self):
        self.ligar()
        self.operador(20)
        self.fusao.adicionar(pessoa())
        self.decidir()
        self.assertEqual(self.ocorrencias(), [])

    def test_triagem_da_ia_nao_descarta_entrada_sem_compra(self):
        self.ligar()
        self.fusao.triagem = TriagemQueAceitaTudo()
        self.fusao.adicionar(pessoa())
        self.decidir()
        self.assertEqual(self.ocorrencias()[0]["situacao"], "aberta")

    def test_operador_filtra_por_tipo(self):
        self.ligar()
        self.fusao.adicionar(pessoa())
        self.fusao.adicionar(pessoa(inicio=2000, fim=2060, pegadas=[2010]))
        self.decidir()
        self.assertEqual([o["tipo"] for o in self.banco.listar_ocorrencias(tipo="sem_compra")["itens"]], ["sem_compra"])
        self.assertEqual([o["tipo"] for o in self.banco.listar_ocorrencias(tipo="suspeita")["itens"]], ["suspeita"])
        self.assertEqual(self.banco.listar_ocorrencias(tipo="qualquer")["total"], 2)


class ConfiguracaoPorLoja(CadastroDeCameras):
    def configurar(self, loja="bologna", **dados):
        return self.cliente.put(f"/api/cameras/lojas/{loja}/recorte-sem-compra", json={"ativo": True, "espera_min": 5, **dados})

    def test_vem_desligado_por_padrao(self):
        self.entrar()
        lojas = {l["id"]: l for l in self.cliente.get("/api/cameras/cadastro").json()["lojas"]}
        self.assertEqual(lojas["bologna"]["recorte_sem_compra"], {"ativo": False, "espera_s": 300})

    def test_admin_liga_vale_na_hora_e_apos_reinicio(self):
        self.entrar()
        self.assertEqual(self.configurar(espera_min=7).status_code, 200)
        self.assertEqual(recorte_sem_compra(self.cfg, "bologna"), {"ativo": True, "espera_s": 420})
        cfg = configuracao_isolada(self.tmp.name)
        aplicar_cadastros(cfg, self.banco)
        self.assertEqual(recorte_sem_compra(cfg, "bologna"), {"ativo": True, "espera_s": 420})
        self.assertFalse(recorte_sem_compra(cfg, "abbott")["ativo"])

    def test_salvar_o_pdv_nao_apaga_o_recorte(self):
        self.entrar()
        self.configurar()
        aplicar_loja_cadastrada(self.cfg, {"chave": "bologna", "nome": "Bologna", "pdv": "42"})
        self.assertTrue(recorte_sem_compra(self.cfg, "bologna")["ativo"])

    def test_valida_espera_e_loja(self):
        self.entrar()
        self.assertEqual(self.configurar(espera_min=0).status_code, 422)
        self.assertEqual(self.configurar(espera_min=61).status_code, 422)
        self.assertEqual(self.configurar(loja="nao-existe").status_code, 404)

    def test_operador_nao_altera(self):
        self.entrar_como_operador()
        self.assertEqual(self.configurar().status_code, 403)


def nome_de_segmento(inicio):
    return datetime.fromtimestamp(inicio, timezone.utc).strftime("%Y-%m-%d_%H-%M-%S-000000+0000") + ".mp4"


class LimpezaDeGravacoes(Base):
    def setUp(self):
        super().setUp()
        self.agora = time.time()
        self.cfg["roteador"]["playback"] = "http://127.0.0.1:9996"
        self.cfg["gravacoes"] = {"pasta": f"{self.tmp.name}/gravacoes"}
        self.em_andamento = None
        self.retencao = Retencao(self.cfg, self.banco, lambda: self.em_andamento)
        self.pasta = self.retencao.pasta / "gravacao" / "bolognalife2"
        self.pasta.mkdir(parents=True)
        self.sendo_gravado = self.segmento(0)

    def segmento(self, minutos_atras):
        inicio = self.agora - minutos_atras * 60 - 60
        arquivo = self.pasta / nome_de_segmento(inicio)
        arquivo.write_bytes(b"x" * 10)
        os.utime(arquivo, (inicio + 60, inicio + 60))
        return arquivo

    def ocorrencia(self, minutos_atras, tipo="suspeita", clipe=None):
        inicio = self.agora - minutos_atras * 60 - 50
        visita = {"id": f"v{minutos_atras}", "loja": "bologna", "inicio": inicio, "fim": inicio + 40,
                  "cameras": ["bolognalife2"], "score": 70, "nivel": "alerta", "motivos": []}
        ocorrencia_id = self.banco.criar_ocorrencia(visita, [], tipo=tipo)
        if clipe:
            self.banco.adicionar_clipe(ocorrencia_id, clipe)

    def test_apaga_na_hora_o_que_nao_tem_ocorrencia(self):
        sem_ocorrencia = self.segmento(2)
        resultado = self.retencao.limpar(self.agora)
        self.assertFalse(sem_ocorrencia.exists())
        self.assertEqual(resultado["apagados"], 1)

    def test_mantem_o_trecho_de_qualquer_ocorrencia(self):
        suspeita, sem_compra, com_clipe = self.segmento(10), self.segmento(20), self.segmento(30)
        self.ocorrencia(10)
        self.ocorrencia(20, tipo="sem_compra")
        self.ocorrencia(30, clipe="clipes/ocorrencia3_bolognalife2.mp4")
        self.retencao.limpar(self.agora)
        self.assertTrue(all(a.exists() for a in (suspeita, sem_compra, com_clipe)))

    def test_nao_apaga_o_segmento_que_o_roteador_esta_gravando(self):
        self.retencao.limpar(self.agora)
        self.assertTrue(self.sendo_gravado.exists())

    def test_mantem_o_que_ainda_nao_foi_decidido(self):
        aguardando = self.segmento(10)
        self.em_andamento = self.agora - 10 * 60 - 30
        self.retencao.limpar(self.agora)
        self.assertTrue(aguardando.exists())

    def test_sem_pasta_configurada_fica_desligada(self):
        self.cfg["gravacoes"] = {"pasta": ""}
        self.assertFalse(Retencao(self.cfg, self.banco).ativa)


if __name__ == "__main__":
    unittest.main()
