import argparse
import logging
import sys

import uvicorn

from . import config as configuracao
from . import migracao
from .banco import Banco
from .cadastro import CadastroCameras
from .notificacoes import Notificador
from .web import criar_app
from .web.contexto import Contexto

log = logging.getLogger("vigia")


def configurar_log():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")


def servir(args):
    import cv2

    from .motor import Motor

    cv2.setNumThreads(1)
    cfg = configuracao.carregar(args.config, args.ambiente)
    for item in args.video:
        nome, _, arquivo = item.partition("=")
        if nome not in cfg["cameras"]:
            raise SystemExit(f"câmera '{nome}' não existe no config")
        caminho = configuracao.caminho_projeto(arquivo)
        if not caminho.is_file():
            raise SystemExit(f"vídeo não encontrado: {caminho}")
        cfg["cameras"][nome]["fonte"] = str(caminho)
        cfg["roteador"]["playback"] = ""
    banco = Banco(cfg["dados"]["banco"])
    if not args.video:
        configuracao.aplicar_cadastros(cfg, banco)
    notificador = Notificador()
    cameras = args.cameras or ([v.partition("=")[0] for v in args.video] if args.video else None)
    motor = None if args.sem_deteccao else Motor(cfg, banco, notificador, cameras).iniciar()
    cadastro = None if args.video else CadastroCameras(cfg, banco, motor).iniciar()
    app = criar_app(Contexto(cfg, banco, notificador, motor, cadastro))
    servidor = cfg["servidor"]
    log.info("%s em http://%s:%s (ambiente %s)", cfg["sistema"]["nome"], servidor["host"], servidor["porta"], cfg["ambiente"])
    try:
        uvicorn.run(app, host=servidor["host"], port=int(servidor["porta"]), log_level="warning",
                    proxy_headers=True, forwarded_allow_ips=servidor.get("proxies_confiaveis", "127.0.0.1"))
    finally:
        if cadastro:
            cadastro.parar()
        if motor:
            motor.parar()


def migrar_dados(args):
    cfg = configuracao.carregar(args.config, args.ambiente)
    try:
        relatorio, simulado = migracao.executar(args.sqlite, cfg["dados"]["banco"], args.substituir, args.simular)
    except migracao.MigracaoRecusada as erro:
        raise SystemExit(str(erro))
    for tabela, origem, destino, situacao in relatorio:
        print(f"{tabela}: {origem} -> {destino} ({situacao})")
    if simulado:
        print("simulação: nada foi gravado no Postgres (rode sem --simular para aplicar)")


def main(argv=None):
    configurar_log()
    parser = argparse.ArgumentParser(prog="vigia", description="Monitoramento de lojas autônomas")
    parser.add_argument("--config", help="arquivo de configuração (padrão: config/vigia.yml)")
    parser.add_argument("--ambiente", help="dev | prod (sobrepõe VIGIA_AMBIENTE)")
    comandos = parser.add_subparsers(dest="comando", required=True)

    servidor = comandos.add_parser("servir", help="sobe a detecção e o painel web")
    servidor.add_argument("--cameras", nargs="+", help="só estas câmeras do config")
    servidor.add_argument("--video", action="append", default=[], metavar="CAMERA=ARQUIVO", help="vídeo no lugar do stream")
    servidor.add_argument("--sem-deteccao", action="store_true", help="só o painel e os registros (sem IA)")
    servidor.set_defaults(executar=servir)

    migrar = comandos.add_parser("migrar-dados", help="copia os dados do SQLite antigo para o Postgres configurado")
    migrar.add_argument("sqlite", help="caminho do arquivo .db do SQLite antigo")
    migrar.add_argument("--substituir", action="store_true", help="apaga o que já existe no Postgres antes de copiar")
    migrar.add_argument("--simular", action="store_true", help="só mostra o que seria feito, sem gravar nada")
    migrar.set_defaults(executar=migrar_dados)

    args = parser.parse_args(argv)
    args.executar(args)


if __name__ == "__main__":
    sys.exit(main())
