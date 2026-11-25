import os
import re
from pathlib import Path
from urllib.parse import urlencode

import yaml

RAIZ = Path(__file__).resolve().parents[1]
VARIAVEL = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def expandir(valor):
    if isinstance(valor, str):
        return VARIAVEL.sub(lambda m: os.environ.get(m[1], m[2] or ""), valor)
    if isinstance(valor, dict):
        return {chave: expandir(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [expandir(item) for item in valor]
    return valor


def ligado(valor):
    if isinstance(valor, str):
        return valor.strip().lower() in ("1", "true", "sim", "yes", "on")
    return bool(valor)


def mesclar(base, extra):
    resultado = dict(base)
    for chave, valor in (extra or {}).items():
        if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
            resultado[chave] = mesclar(resultado[chave], valor)
        else:
            resultado[chave] = valor
    return resultado


def caminho_projeto(caminho):
    caminho = Path(caminho)
    return caminho if caminho.is_absolute() else RAIZ / caminho


def carregar_env(arquivo):
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def fonte_da_camera(camera, roteador):
    if camera.get("fonte"):
        return camera["fonte"]
    if roteador.get("rtsp"):
        return f"{roteador['rtsp'].rstrip('/')}/{camera['caminho']}"
    url = f"{roteador['rtmp'].rstrip('/')}/{camera['caminho']}"
    if roteador.get("usuario"):
        url += "?" + urlencode({"user": roteador["usuario"], "pass": roteador.get("senha", "")})
    return url


def carregar(caminho=None, ambiente=None):
    caminho = Path(caminho or os.environ.get("VIGIA_CONFIG") or RAIZ / "vigia.yml")
    carregar_env(Path(os.environ.get("VIGIA_ENV") or RAIZ / ".env"))
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))

    ambiente = ambiente or os.environ.get("VIGIA_AMBIENTE") or dados.get("ambiente", "dev")
    ambientes = dados.pop("ambientes", {}) or {}
    if ambiente not in ambientes:
        raise SystemExit(f"Ambiente '{ambiente}' não existe em {caminho} (disponíveis: {', '.join(ambientes)})")
    cfg = expandir(mesclar(dados, ambientes[ambiente]))
    cfg["ambiente"] = ambiente

    cfg["dados"] = {chave: (valor if chave == "banco" else str(caminho_projeto(valor)))
                   for chave, valor in cfg["dados"].items()}
    for nome, camera in cfg["cameras"].items():
        preparar_camera(cfg, nome, camera)
    return cfg


def preparar_camera(cfg, nome, camera):
    camera["nome"] = nome
    camera.setdefault("descricao", nome)
    prefixo = cfg["roteador"].get("prefixo_gravacao") or "gravacao"
    camera.setdefault("caminho_gravacao", prefixo + "/" + camera["caminho"].split("/", 1)[-1])
    camera["fonte"] = fonte_da_camera(camera, cfg["roteador"])
    return camera


def aplicar_loja_cadastrada(cfg, loja):
    lojas = cfg.setdefault("lojas", {})
    lojas[loja["chave"]] = {**(lojas.get(loja["chave"]) or {}), "nome": loja["nome"], "pdv": loja.get("pdv") or "", "cadastrada": True}


def aplicar_camera_cadastrada(cfg, camera):
    cfg["cameras"][camera["nome"]] = preparar_camera(cfg, camera["nome"], {
        "descricao": camera.get("descricao") or camera["nome"], "caminho": camera["caminho"], "loja": camera["loja"],
        "cobre_totem": "auto", "cadastrada": True})


def aplicar_recorte_sem_compra(cfg, loja, recorte):
    if loja in (cfg.get("lojas") or {}):
        cfg["lojas"][loja]["recorte_sem_compra"] = {"ativo": bool(recorte["ativo"]), "espera_s": int(recorte["espera_s"])}


def recorte_sem_compra(cfg, loja):
    padrao = {"ativo": False, "espera_s": cfg["fusao"]["sem_compra"]["espera_padrao_s"]}
    return ((cfg.get("lojas") or {}).get(loja) or {}).get("recorte_sem_compra") or padrao


def aplicar_cadastros(cfg, banco):
    for loja in banco.listar_lojas_cadastradas():
        aplicar_loja_cadastrada(cfg, loja)
    for camera in banco.listar_cameras_cadastradas():
        aplicar_camera_cadastrada(cfg, camera)
    for loja, recorte in banco.recortes_sem_compra().items():
        aplicar_recorte_sem_compra(cfg, loja, recorte)


def pdvs_da_loja(cfg, loja):
    valor = ((cfg.get("lojas") or {}).get(loja) or {}).get("pdv")
    itens = valor if isinstance(valor, list) else str(valor or "").split(",")
    return [str(pdv).strip() for pdv in itens if str(pdv).strip()]


def pdvs_configurados(cfg):
    return sorted({int(pdv) for loja in cfg.get("lojas") or {} for pdv in pdvs_da_loja(cfg, loja)})


def nome_da_loja(cfg, loja):
    return ((cfg.get("lojas") or {}).get(loja) or {}).get("nome") or loja
