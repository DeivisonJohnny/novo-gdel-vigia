import importlib.util
import ipaddress
import logging
import re
import secrets
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode

import httpx
import yaml

from .config import (aplicar_camera_cadastrada, aplicar_loja_cadastrada, aplicar_recorte_sem_compra, caminho_projeto, nome_da_loja,
                     pdvs_da_loja, recorte_sem_compra)

log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

CODIGO_VALIDO = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
PREFIXO_AO_VIVO = "live/"
TAMANHO_SENHA_BYTES = 12
INTERVALO_SINCRONIA_S = 60
TIMEOUT_API_S = 10
RTMP_PUBLICO_PADRAO = "rtmp://IP_DO_SERVIDOR:1945"
GERADOR_DO_ROTEADOR = "../roteador/gerar.py"


class CadastroInvalido(ValueError):
    pass


class RoteadorIndisponivel(RuntimeError):
    pass


def chave_da_loja(nome):
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def _carregar_gerador():
    especificacao = importlib.util.spec_from_file_location("gerador_roteador", caminho_projeto(GERADOR_DO_ROTEADOR))
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def _publicador(camera):
    return {"user": camera["usuario"], "pass": camera["senha"], "ips": [],
            "permissions": [{"action": "publish", "path": camera["caminho"]}]}


def _rede(ip):
    try:
        return str(ipaddress.ip_network(ip, strict=False))
    except ValueError:
        return ip


def _assinatura_usuarios(usuarios):
    return sorted((u.get("user"), tuple(sorted(_rede(ip) for ip in u.get("ips") or [])),
                   tuple(sorted(f"{p.get('action')}:{p.get('path', '')}" for p in u.get("permissions") or [])))
                  for u in usuarios)


def _nome_do_pdv(pdv):
    partes = [str(pdv[campo]).strip() for campo in ("localCustomerName", "localName", "specificLocation") if pdv.get(campo)]
    return " · ".join(dict.fromkeys(partes)) or f"PDV {pdv['id']}"


class Roteador:
    def __init__(self, cfg):
        self.api = (cfg["roteador"].get("api") or "").rstrip("/")
        self.config_gerada = cfg["roteador"].get("config_gerada") or ""
        self._gerador = None

    @property
    def disponivel(self):
        return bool(self.api and self.config_gerada)

    def _chamar(self, metodo, caminho, corpo=None):
        try:
            resposta = httpx.request(metodo, f"{self.api}{caminho}", json=corpo, timeout=TIMEOUT_API_S)
        except httpx.HTTPError as erro:
            raise RoteadorIndisponivel(f"API do roteador fora do ar ({type(erro).__name__})")
        if resposta.status_code >= 400:
            raise RoteadorIndisponivel(f"roteador recusou {metodo} {caminho}: {resposta.status_code} {resposta.text[:200]}")
        return resposta.json() if resposta.content else None

    def _base(self):
        arquivo = caminho_projeto(self.config_gerada)
        if not Path(arquivo).is_file():
            raise RoteadorIndisponivel(f"configuração gerada do roteador não encontrada em {arquivo}")
        return yaml.safe_load(Path(arquivo).read_text(encoding="utf-8"))

    def _caminhos_desejados(self, base, cameras):
        self._gerador = self._gerador or _carregar_gerador()
        porta_rtsp = int(str(base["rtspAddress"]).rsplit(":", 1)[-1])
        return self._gerador.caminhos_das_cameras(cameras, porta_rtsp, [], bool(base.get("playback")))

    def sincronizar(self, cameras, removidas=()):
        base = self._base()
        self._sincronizar_usuarios(base, cameras)
        self._sincronizar_caminhos(base, cameras, removidas)

    def _sincronizar_usuarios(self, base, cameras):
        desejados = list(base.get("authInternalUsers") or []) + [_publicador(c) for c in cameras]
        atuais = (self._chamar("GET", "/v3/config/global/get") or {}).get("authInternalUsers") or []
        if _assinatura_usuarios(atuais) != _assinatura_usuarios(desejados):
            self._chamar("PATCH", "/v3/config/global/patch", {"authInternalUsers": desejados})

    def _sincronizar_caminhos(self, base, cameras, removidas):
        existentes = {item["name"] for item in (self._chamar("GET", "/v3/config/paths/list?itemsPerPage=1000") or {}).get("items") or []}
        caminhos_removidos = self._caminhos_desejados(base, removidas) if removidas else {}
        for nome in caminhos_removidos:
            if nome in existentes:
                self._chamar("DELETE", f"/v3/config/paths/delete/{nome}")
        for nome, conf in self._caminhos_desejados(base, cameras).items():
            if nome not in existentes:
                self._chamar("POST", f"/v3/config/paths/add/{nome}", conf)


class CadastroCameras:
    def __init__(self, cfg, banco, motor=None):
        self.cfg = cfg
        self.banco = banco
        self.motor = motor
        self.roteador = Roteador(cfg)
        self.lock = threading.Lock()
        self.erro_roteador = ""
        self.sincronizado_em = None
        self._parar = threading.Event()

    def iniciar(self):
        if self.roteador.disponivel:
            threading.Thread(target=self._manter_sincronizado, name="cadastro-roteador", daemon=True).start()
        return self

    def parar(self):
        self._parar.set()

    def _manter_sincronizado(self):
        while not self._parar.is_set():
            self.sincronizar()
            self._parar.wait(INTERVALO_SINCRONIA_S)

    def sincronizar(self, removidas=()):
        if not self.roteador.disponivel:
            self.erro_roteador = "API do roteador não configurada neste ambiente"
            return False
        try:
            with self.lock:
                self.roteador.sincronizar(self.banco.listar_cameras_cadastradas(), removidas)
        except (RoteadorIndisponivel, OSError, KeyError, ValueError) as erro:
            self.erro_roteador = str(erro)
            log.warning("não foi possível sincronizar câmeras no roteador: %s", erro)
            return False
        self.erro_roteador = ""
        self.sincronizado_em = time.time()
        return True

    def url_rtmp(self, camera):
        base = (self.cfg["roteador"].get("rtmp_publico") or RTMP_PUBLICO_PADRAO).rstrip("/")
        return f"{base}/{camera['caminho']}?{urlencode({'user': camera['usuario'], 'pass': camera['senha']})}"

    def listar(self):
        cadastradas = {c["nome"]: c for c in self.banco.listar_cameras_cadastradas()}
        marcadas = self.banco.maquininhas_marcadas()
        return {
            "roteador": {"disponivel": self.roteador.disponivel, "erro": self.erro_roteador, "sincronizado_em": self.sincronizado_em},
            "rtmp_publico_configurado": bool(self.cfg["roteador"].get("rtmp_publico")),
            "lojas": [{"id": chave, "nome": loja.get("nome") or chave, "pdv": str(loja.get("pdv") or ""),
                       "recorte_sem_compra": recorte_sem_compra(self.cfg, chave)}
                      for chave, loja in (self.cfg.get("lojas") or {}).items()],
            "cameras": [{"nome": nome, "descricao": camera.get("descricao", nome), "loja": camera.get("loja"),
                         "loja_nome": nome_da_loja(self.cfg, camera.get("loja")), "caminho": camera["caminho"],
                         "cadastrada": nome in cadastradas,
                         "url": self.url_rtmp(cadastradas[nome]) if nome in cadastradas else None,
                         "maquininhas": marcadas.get(nome)}
                        for nome, camera in self.cfg["cameras"].items()],
        }

    def definir_pdv(self, chave, pdv):
        loja = (self.cfg.get("lojas") or {}).get(chave)
        if loja is None:
            raise CadastroInvalido("loja não encontrada")
        registro = {"chave": chave, "nome": loja.get("nome") or chave, "pdv": pdv.strip()}
        self.banco.salvar_loja_cadastrada(**registro)
        aplicar_loja_cadastrada(self.cfg, registro)
        if self.motor:
            self.motor.touchpay.atualizar_lojas(self.cfg)
        return registro

    def configurar_recorte_sem_compra(self, chave, ativo, espera_s, usuario):
        if chave not in (self.cfg.get("lojas") or {}):
            raise CadastroInvalido("loja não encontrada")
        self.banco.configurar_recorte_sem_compra(chave, ativo, espera_s, usuario)
        aplicar_recorte_sem_compra(self.cfg, chave, {"ativo": ativo, "espera_s": espera_s})
        return {"id": chave, "recorte_sem_compra": recorte_sem_compra(self.cfg, chave)}

    def pdvs_touchpay(self):
        cliente = self.motor.touchpay.cliente if self.motor else None
        if not cliente:
            return []
        em_uso = {pdv: chave for chave in self.cfg.get("lojas") or {} for pdv in pdvs_da_loja(self.cfg, chave)}
        return [{"id": str(pdv["id"]), "nome": _nome_do_pdv(pdv), "loja": em_uso.get(str(pdv["id"]))}
                for pdv in cliente.get("/api/public/pointsOfSale") or [] if pdv.get("id") is not None and not pdv.get("closingDate")]

    def _loja_para(self, loja, nova_loja):
        if nova_loja:
            nome = nova_loja["nome"].strip()
            chave = chave_da_loja(nome)
            if not chave:
                raise CadastroInvalido("nome da loja inválido")
            if chave in (self.cfg.get("lojas") or {}):
                raise CadastroInvalido(f"já existe a loja '{nome_da_loja(self.cfg, chave)}': escolha-a na lista")
            registro = {"chave": chave, "nome": nome, "pdv": (nova_loja.get("pdv") or "").strip()}
            self.banco.salvar_loja_cadastrada(**registro)
            aplicar_loja_cadastrada(self.cfg, registro)
            return chave
        if loja not in (self.cfg.get("lojas") or {}):
            raise CadastroInvalido("loja não encontrada")
        return loja

    def criar(self, codigo, descricao="", loja=None, nova_loja=None):
        codigo = (codigo or "").strip()
        if not CODIGO_VALIDO.match(codigo):
            raise CadastroInvalido("o código deve ter de 3 a 40 letras, números, '-' ou '_'")
        nome = codigo.lower()
        if nome in self.cfg["cameras"]:
            raise CadastroInvalido(f"a câmera {codigo} já está cadastrada")
        chave_loja = self._loja_para(loja, nova_loja)
        camera = {"nome": nome, "descricao": descricao.strip() or f"{nome_da_loja(self.cfg, chave_loja)} · {codigo}",
                  "loja": chave_loja, "caminho": PREFIXO_AO_VIVO + nome, "usuario": nome,
                  "senha": secrets.token_hex(TAMANHO_SENHA_BYTES)}
        self.banco.salvar_camera_cadastrada(camera)
        aplicar_camera_cadastrada(self.cfg, camera)
        roteador_ok = self.sincronizar()
        if self.motor:
            self.motor.adicionar_camera(nome)
        return {"nome": nome, "url": self.url_rtmp(camera), "roteador_ok": roteador_ok, "erro_roteador": self.erro_roteador}

    def remover(self, nome):
        camera = next((c for c in self.banco.listar_cameras_cadastradas() if c["nome"] == nome), None)
        if not camera:
            raise CadastroInvalido("só dá para remover câmeras cadastradas pelo painel")
        if self.motor:
            self.motor.remover_camera(nome)
        self.banco.remover_camera_cadastrada(nome)
        self.banco.remover_maquininhas(nome)
        self.cfg["cameras"].pop(nome, None)
        return {"roteador_ok": self.sincronizar(removidas=[camera])}
