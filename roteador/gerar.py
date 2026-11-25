import argparse
import os
import re
import shlex
import sys
from pathlib import Path

import yaml

PASTA = Path(__file__).resolve().parent
VARIAVEL = re.compile(r"\$\{(\w+)\}")
LOCAL = "127.0.0.1"
FFMPEG_LEITURA = ("ffmpeg -nostdin -loglevel error -rtsp_transport tcp -timeout 10000000 -analyzeduration 2000000 "
                  "-probesize 1000000 -use_wallclock_as_timestamps 1")


def carregar_env(caminho):
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def expandir(texto, faltando):
    def trocar(achado):
        valor = os.environ.get(achado[1], "")
        if not valor:
            faltando.add(achado[1])
        return valor
    return VARIAVEL.sub(trocar, texto)


def caminho_gravacao(caminho):
    return "gravacao/" + caminho.split("/", 1)[-1]


def comando_reenvio(porta_rtsp, caminho, destinos, gravar):
    saidas = [f"[f=rtsp:rtsp_transport=tcp]rtsp://{LOCAL}:{porta_rtsp}/{caminho_gravacao(caminho)}"] if gravar else []
    saidas += [f"[f=flv:onfail=ignore]{destino.replace('{caminho}', caminho)}" for destino in destinos]
    return f"{FFMPEG_LEITURA} -i rtsp://{LOCAL}:{porta_rtsp}/{caminho} -map 0:v -c copy -f tee {shlex.quote('|'.join(saidas))}"


def usuarios_do_roteador(cameras, leitores, ip_backend=None):
    publicadores = [{"user": c["usuario"], "pass": c["senha"], "ips": [], "permissions": [{"action": "publish", "path": c["caminho"]}]}
                    for c in cameras]
    externos = [{"user": l["usuario"], "pass": l["senha"], "ips": l.get("ips") or [],
                 "permissions": [{"action": "read"}, {"action": "playback"}]} for l in leitores]
    maquina_local = {"user": "any", "pass": "", "ips": [LOCAL],
                     "permissions": [{"action": "read"}, {"action": "playback"}, {"action": "api"},
                                     {"action": "publish", "path": "~^gravacao/"}]}
    backend = [{"user": "any", "pass": "", "ips": [ip_backend],
                "permissions": [{"action": "read"}, {"action": "playback"}, {"action": "api"}]}] if ip_backend else []
    return publicadores + externos + [maquina_local] + backend


def opcoes_webrtc(webrtc, escuta=LOCAL):
    hosts_publicos = [str(h) for h in webrtc.get("hosts_publicos") or []]
    expor_midia = bool(hosts_publicos) or escuta != LOCAL
    opcoes = {
        "webrtc": True,
        "webrtcAddress": f"{escuta}:{webrtc['porta']}",
        "webrtcLocalUDPAddress": f"{'' if expor_midia else LOCAL}:{webrtc['udp']}",
        "webrtcIPsFromInterfaces": False,
        "webrtcAdditionalHosts": hosts_publicos or [LOCAL],
        "webrtcAllowOrigins": webrtc.get("origens") or ["*"],
    }
    if expor_midia and webrtc.get("tcp"):
        opcoes["webrtcLocalTCPAddress"] = f":{webrtc['tcp']}"
    return opcoes


def caminhos_das_cameras(cameras, porta_rtsp, destinos, gravar):
    caminhos = {}
    for camera in cameras:
        caminho = {"record": False}
        if destinos or gravar:
            caminho["runOnAvailable"] = comando_reenvio(porta_rtsp, camera["caminho"], destinos, gravar)
            caminho["runOnAvailableRestart"] = True
        caminhos[camera["caminho"]] = caminho
        if gravar:
            caminhos[caminho_gravacao(camera["caminho"])] = {"record": True}
    return caminhos


def ajustar_para_docker(r, args):
    hosts = [h.strip() for h in (args.hosts_publicos or "").split(",") if h.strip()]
    r["webrtc"].update({"hosts_publicos": hosts, "udp": args.webrtc_udp or r["webrtc"]["udp"],
                        "tcp": args.webrtc_tcp or r["webrtc"]["tcp"]})
    return r


def montar(r, docker=False, ip_backend=None):
    escuta = "" if docker else LOCAL
    portas, gravacao = r["portas"], r["gravacao"]
    cameras = list(r["cameras"].values())
    destinos = [d["url"] for d in r.get("destinos") or [] if d.get("ativo")]
    gravar = bool(gravacao.get("ativa"))
    return {
        "logLevel": "info",
        "readTimeout": "30s",
        "writeTimeout": "30s",
        "hls": False, "srt": False, "moq": False,
        "rtsp": True, "rtspTransports": ["tcp"], "rtspAddress": f"{escuta}:{portas['rtsp']}",
        "rtpAddress": f"{LOCAL}:8000", "rtcpAddress": f"{LOCAL}:8001",
        **opcoes_webrtc(r["webrtc"], escuta),
        "rtmp": True, "rtmpAddress": f":{portas['rtmp']}",
        "api": True, "apiAddress": f"{escuta}:{portas['api']}",
        "playback": gravar, "playbackAddress": f"{escuta}:{portas['playback']}",
        "authMethod": "internal",
        "authInternalUsers": usuarios_do_roteador(cameras, r.get("leitores") or [], ip_backend if docker else None),
        "pathDefaults": {
            "record": False,
            "recordPath": f"{gravacao['pasta'].rstrip('/')}/%path/%Y-%m-%d_%H-%M-%S-%f%z",
            "recordFormat": "fmp4",
            "recordSegmentDuration": gravacao["segmento"],
            "recordDeleteAfter": gravacao["manter"],
        },
        "paths": caminhos_das_cameras(cameras, portas["rtsp"], destinos, gravar),
    }, len(destinos)


def senhas_obrigatorias_vazias(r):
    senhas = [c["senha"] for c in r["cameras"].values()] + [l["senha"] for l in r.get("leitores") or []]
    return any(not s for s in senhas)


def main():
    parser = argparse.ArgumentParser(description="Gera o mediamtx.yml do roteador de vídeo")
    parser.add_argument("--entrada", default=PASTA / "roteador.yml")
    parser.add_argument("--saida", default=PASTA / "mediamtx.yml")
    parser.add_argument("--ip", default="IP_DO_SERVIDOR", help="IP público, só para imprimir a URL de cada câmera")
    parser.add_argument("--docker", action="store_true", help="roteador num container, lido pelo backend pela rede do compose")
    parser.add_argument("--ip-backend", default="", help="IP fixo do backend na rede do compose, único que lê sem senha")
    parser.add_argument("--hosts-publicos", default="", help="IPs ou nomes, separados por vírgula, anunciados no WebRTC")
    parser.add_argument("--webrtc-udp", type=int, default=0)
    parser.add_argument("--webrtc-tcp", type=int, default=0)
    parser.add_argument("--porta-rtmp-publica", type=int, default=0, help="porta RTMP vista pelas câmeras, só para imprimir")
    args = parser.parse_args()
    if args.docker and not args.ip_backend:
        parser.error("--docker precisa de --ip-backend")

    carregar_env(PASTA / ".env")
    faltando = set()
    r = yaml.safe_load(expandir(Path(args.entrada).read_text(encoding="utf-8"), faltando))
    if senhas_obrigatorias_vazias(r):
        print(f"Faltam variáveis: {', '.join(sorted(faltando))} (defina em roteador/.env)", file=sys.stderr)
        sys.exit(1)

    if args.docker:
        r = ajustar_para_docker(r, args)
    mediamtx, total_destinos = montar(r, args.docker, args.ip_backend)
    saida = Path(args.saida)
    saida.write_text(yaml.safe_dump(mediamtx, sort_keys=False, allow_unicode=True), encoding="utf-8")
    saida.chmod(0o600)
    print(f"{saida} gerado ({len(r['cameras'])} câmeras, {total_destinos} destino(s) de reenvio)")
    hosts = r["webrtc"].get("hosts_publicos") or []
    print(f"WebRTC: {'mídia exposta em ' + ', '.join(map(str, hosts)) if hosts else 'só nesta máquina'}")
    print("\nURL para o app de cada câmera (RTMP personalizado):")
    for camera in r["cameras"].values():
        porta = args.porta_rtmp_publica or r["portas"]["rtmp"]
        print(f"  {camera['caminho']}: rtmp://{args.ip}:{porta}/{camera['caminho']}?user={camera['usuario']}&pass=<senha>")


if __name__ == "__main__":
    main()
