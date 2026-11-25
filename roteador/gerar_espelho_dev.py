"""Gera o mediamtx.yml do roteador LOCAL de desenvolvimento.

Este roteador não recebe publicação de câmeras: ele puxa (source pull) o
vídeo de cada câmera direto do roteador de PRODUÇÃO (rtmp://IP:PORTA) e
grava localmente, dando ao `visao` em dev uma API de playback própria —
igual à que existe em produção, mas com gravações isoladas na sua máquina.

Nunca escreve nem altera nada no servidor de produção: só lê o RTMP público
das câmeras (usuário "leitor", somente leitura).

Uso:
    python roteador/gerar_espelho_dev.py

Variáveis de ambiente (lidas de .env na raiz do projeto, ou já exportadas):
    VIGIA_IP_PUBLICO       IP do roteador de produção
    VIGIA_PORTA_RTMP       porta RTMP pública de produção (padrão 1945)
    VIGIA_LEITOR_SENHA     senha do usuário "leitor" no roteador de produção
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import yaml

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
SAIDA = PASTA / "mediamtx.yml"

CAMERAS = ["bolognalife2", "bolognalife2b", "itacolomi", "abbott1", "abbott2"]


def carregar_env(caminho):
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def main():
    carregar_env(RAIZ / ".env")
    ip = os.environ.get("VIGIA_IP_PUBLICO", "")
    porta = os.environ.get("VIGIA_PORTA_RTMP", "1945")
    senha = os.environ.get("VIGIA_LEITOR_SENHA", "")
    if not ip or not senha:
        print("Faltam VIGIA_IP_PUBLICO / VIGIA_LEITOR_SENHA (defina em .env na raiz do projeto)", file=sys.stderr)
        sys.exit(1)

    consulta = urlencode({"user": "leitor", "pass": senha})
    paths = {
        f"live/{camera}": {
            "source": f"rtmp://{ip}:{porta}/live/{camera}?{consulta}",
            "sourceOnDemand": False,
            "record": True,
        }
        for camera in CAMERAS
    }

    mediamtx = {
        "logLevel": "info",
        "readTimeout": "30s",
        "writeTimeout": "30s",
        "hls": False, "srt": False, "moq": False,
        "rtsp": True, "rtspTransports": ["tcp"], "rtspAddress": ":8554",
        "webrtc": True, "webrtcAddress": ":8889",
        "webrtcLocalUDPAddress": ":8189", "webrtcLocalTCPAddress": ":8190",
        "webrtcIPsFromInterfaces": True, "webrtcAllowOrigins": ["*"],
        "rtmp": True, "rtmpAddress": ":1935",
        "api": True, "apiAddress": ":9997",
        "playback": True, "playbackAddress": ":9996",
        "authMethod": "internal",
        "authInternalUsers": [
            {"user": "any", "pass": "", "ips": [],
             "permissions": [{"action": "publish"}, {"action": "read"}, {"action": "playback"}, {"action": "api"}]},
        ],
        "pathDefaults": {
            "record": False,
            "recordPath": "/gravacoes/%path/%Y-%m-%d_%H-%M-%S-%f%z",
            "recordFormat": "fmp4",
            "recordSegmentDuration": "60s",
            "recordDeleteAfter": "48h",
        },
        "paths": paths,
    }
    SAIDA.write_text(yaml.safe_dump(mediamtx, sort_keys=False, allow_unicode=True), encoding="utf-8")
    SAIDA.chmod(0o600)
    print(f"{SAIDA} gerado ({len(CAMERAS)} câmera(s) espelhadas de {ip}:{porta})")


if __name__ == "__main__":
    main()
