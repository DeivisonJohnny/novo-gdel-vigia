import base64
import json
import logging
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from .config import pdvs_configurados, pdvs_da_loja

log = logging.getLogger(__name__)

TAMANHO_PAGINA = 1000
MAX_PAGINAS = 20
RENOVAR_TOKEN_ANTES_S = 300
MAX_HISTORICO_API_S = 89 * 86400
METODOS_APP = {"AppSale", "AppPix", "AppCreditCard", "ExternalApp", "Wallet", "RemoteCredit"}
OPERACOES_HUMANAS = {"Correction", "Full", "PickList", "Repositioning", "PlanogramChange", "Supply", "Expired",
                     "Damaged", "Return", "RemovedFromInventory", "Picking", "PickingReturn", "CheckingAdjustment",
                     "Transfer", "Verified", "UseAndConsumption", "Other", "Operation"}
OPERACOES_CONTAGEM = {"Correction", "Full", "CheckingAdjustment", "DifferentQuantity", "ZeroStock", "Verified"}


def expiracao_jwt(token):
    try:
        carga = token.split(".")[1]
        carga += "=" * (-len(carga) % 4)
        return float(json.loads(base64.urlsafe_b64decode(carga)).get("exp") or 0)
    except (IndexError, ValueError):
        return 0.0


def valor_em(dados, caminho):
    atual = dados
    for parte in str(caminho).split("."):
        atual = atual.get(parte) if isinstance(atual, dict) else None
    return atual


class ClienteTouchPay:
    def __init__(self, c):
        self.url = c["url"].rstrip("/")
        self.auth = c.get("autenticacao") or {}
        self.token = (self.auth.get("token") or "").removeprefix("Bearer ").strip()
        self.sessao = requests.Session()
        self.lock = threading.Lock()

    def _login(self):
        email, senha, caminho = self.auth.get("email"), self.auth.get("senha"), self.auth.get("login_caminho")
        if not (email and senha and caminho):
            return False
        resposta = self.sessao.post(f"{self.url}/{caminho.lstrip('/')}", json={"email": email, "password": senha}, timeout=20)
        resposta.raise_for_status()
        try:
            corpo = resposta.json()
            token = valor_em(corpo, self.auth.get("campo_token") or "token") if isinstance(corpo, dict) else corpo
        except ValueError:
            token = resposta.text
        self.token = str(token or "").removeprefix("Bearer ").strip().strip('"')
        return bool(self.token)

    def _cabecalhos(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        if self.auth.get("email") and self.auth.get("senha"):
            basico = base64.b64encode(f"{self.auth['email']}:{self.auth['senha']}".encode()).decode()
            return {"Authorization": f"Basic {basico}"}
        raise RuntimeError("TouchPay sem credencial (TOUCHPAY_TOKEN ou TOUCHPAY_EMAIL/TOUCHPAY_SENHA)")

    def _token_vencendo(self):
        expira = expiracao_jwt(self.token) if self.token else 0
        return not self.token or (expira and expira - time.time() < RENOVAR_TOKEN_ANTES_S)

    def get(self, caminho, parametros=None):
        with self.lock:
            if self._token_vencendo() and self.auth.get("login_caminho"):
                self._login()
            resposta = self.sessao.get(f"{self.url}{caminho}", params=parametros, headers=self._cabecalhos(), timeout=30)
            if resposta.status_code == 401 and self._login():
                resposta = self.sessao.get(f"{self.url}{caminho}", params=parametros, headers=self._cabecalhos(), timeout=30)
            resposta.raise_for_status()
            return resposta.json()

    def paginado(self, caminho, parametros):
        for pagina in range(1, MAX_PAGINAS + 1):
            dados = self.get(caminho, {**parametros, "Page": pagina, "PageSize": TAMANHO_PAGINA})
            yield from dados.get("items") or []
            if not dados.get("hasNextPage"):
                return


class TouchPay:
    def __init__(self, cfg, banco):
        self.c = cfg["touchpay"]
        self.fuso_api = ZoneInfo(self.c.get("fuso_api") or cfg["sistema"]["fuso"])
        self.banco = banco
        self.atualizar_lojas(cfg)
        self.inventarios = {}
        self.cliente = ClienteTouchPay(self.c) if self.c.get("url") else None
        self.recebidos = 0
        self.ultimo_recebido = None
        self.ultima_consulta = None
        self.erro_vendas = ""
        self.erro_estoque = ""

    def atualizar_lojas(self, cfg):
        self.pdvs = pdvs_configurados(cfg)
        self.loja_do_pdv = {pdv: loja for loja in cfg.get("lojas") or {} for pdv in pdvs_da_loja(cfg, loja)}

    def horario(self, valor):
        if not valor:
            return None
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return (data if data.tzinfo else data.replace(tzinfo=self.fuso_api)).timestamp()

    @staticmethod
    def iso(t):
        return datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")

    def normalizar(self, t):
        if not t.get("uuid"):
            return None
        pdv = str(t["pointOfSaleId"]) if t.get("pointOfSaleId") is not None else None
        if self.pdvs and pdv is not None and int(pdv) not in self.pdvs:
            return None
        itens = [{"produto_id": i.get("productId"), "descricao": i.get("productDescription"),
                  "quantidade": int(i.get("quantity") or 1), "preco": i.get("price")} for i in t.get("items") or []]
        return {
            "id": str(t["uuid"]),
            "horario": self.horario(t.get("date")) or time.time(),
            "valor": t.get("paymentAmount") if t.get("paymentAmount") is not None else t.get("totalPrice"),
            "situacao": "aprovado",
            "qtd_itens": sum(i["quantidade"] for i in itens) if itens else None,
            "pdv": pdv,
            "loja": self.loja_do_pdv.get(pdv),
            "metodo": t.get("paymentMethod"),
            "itens": itens,
        }

    def registrar(self, transacoes):
        salvos = 0
        for transacao in transacoes or []:
            pagamento = self.normalizar(transacao) if isinstance(transacao, dict) else None
            if pagamento:
                self.banco.salvar_pagamento(pagamento)
                salvos += 1
        if salvos:
            self.recebidos += salvos
            self.ultimo_recebido = time.time()
        return salvos

    def normalizar_movimentacao(self, m, pdv=None):
        return {
            "pdv": str(pdv) if pdv is not None else None,
            "id": int(m["id"]), "data": self.horario(m.get("date")), "tipo": m.get("type"),
            "produto_id": m.get("productId"), "quantidade": m.get("changeAmount"), "final": m.get("finalAmount"),
            "usuario": m.get("userEmail"),
            "humana": m.get("type") in OPERACOES_HUMANAS,
            "contagem": m.get("type") in OPERACOES_CONTAGEM,
        }

    def iniciar(self):
        if self.cliente is None:
            log.warning("TouchPay sem touchpay.url: pagamentos não serão lidos")
            return
        threading.Thread(target=self._repetir, args=(self.consultar_vendas, "erro_vendas", self.c.get("intervalo_s", 20)),
                         name="touchpay-vendas", daemon=True).start()
        estoque = self.c.get("estoque") or {}
        if estoque.get("ativo"):
            threading.Thread(target=self._repetir, args=(self.consultar_estoque, "erro_estoque", estoque.get("intervalo_s", 120)),
                             name="touchpay-estoque", daemon=True).start()

    def _repetir(self, tarefa, campo_erro, intervalo_s):
        while True:
            try:
                tarefa()
                setattr(self, campo_erro, "")
            except Exception as erro:
                setattr(self, campo_erro, f"{type(erro).__name__}: {str(erro)[:200]}")
                log.warning("TouchPay %s: %s", tarefa.__name__, getattr(self, campo_erro))
            time.sleep(float(intervalo_s))

    def consultar_vendas(self, agora=None):
        agora = agora or time.time()
        ultimo = self.banco.ultimo_horario_pagamento()
        desde = (ultimo or agora - self.c.get("carga_inicial_h", 2) * 3600) - self.c.get("releitura_min", 10) * 60
        parametros = {"MinDate": self.iso(max(desde, agora - MAX_HISTORICO_API_S))}
        if len(self.pdvs) == 1:
            parametros["PointOfSaleId"] = self.pdvs[0]
        salvos = self.registrar(list(self.cliente.paginado("/api/public/transactions", parametros)))
        self.ultima_consulta = agora
        return salvos

    def _descobrir_inventarios(self):
        if self.pdvs and len(self.inventarios) < len(self.pdvs):
            for pdv in self.cliente.get("/api/public/pointsOfSale"):
                if pdv.get("id") in self.pdvs and pdv.get("inventoryId"):
                    self.inventarios[pdv["id"]] = pdv["inventoryId"]
        return self.inventarios

    def consultar_estoque(self, agora=None):
        agora = agora or time.time()
        desde = self.iso(self.banco.ultima_movimentacao() or agora - 7 * 86400)
        total = 0
        for pdv, inventario in list(self._descobrir_inventarios().items()) or [(None, None)]:
            parametros = {"MinDate": desde, **({"InventoryId": inventario} if inventario else {})}
            movimentacoes = [self.normalizar_movimentacao(m, pdv)
                             for m in self.cliente.paginado("/api/public/inventory/transactions", parametros)]
            self.banco.salvar_movimentacoes(movimentacoes)
            total += len(movimentacoes)
        return total

    def status(self):
        return {
            "configurado": self.cliente is not None,
            "pdvs": self.pdvs,
            "recebidos": self.recebidos,
            "ultimo_recebido": self.ultimo_recebido,
            "ultima_consulta": self.ultima_consulta,
            "erro_vendas": self.erro_vendas,
            "erro_estoque": self.erro_estoque,
        }
