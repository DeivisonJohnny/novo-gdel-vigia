import asyncio
import itertools
import threading
import time
from collections import deque

MAX_RECENTES = 100
TAMANHO_FILA_ASSINANTE = 200


class Notificador:
    def __init__(self):
        self.lock = threading.Lock()
        self.assinantes = set()
        self.recentes = deque(maxlen=MAX_RECENTES)
        self._sequencia = itertools.count(1)

    def publicar(self, tipo, dados):
        mensagem = {"id": next(self._sequencia), "tipo": tipo, "t": time.time(), "dados": dados}
        with self.lock:
            self.recentes.append(mensagem)
            assinantes = list(self.assinantes)
        for loop, fila in assinantes:
            loop.call_soon_threadsafe(self._entregar, fila, mensagem)

    @staticmethod
    def _entregar(fila, mensagem):
        if fila.full():
            fila.get_nowait()
        fila.put_nowait(mensagem)

    def assinar(self):
        fila = asyncio.Queue(maxsize=TAMANHO_FILA_ASSINANTE)
        assinatura = (asyncio.get_running_loop(), fila)
        with self.lock:
            self.assinantes.add(assinatura)
        return assinatura

    def cancelar(self, assinatura):
        with self.lock:
            self.assinantes.discard(assinatura)

    def depois_de(self, ultimo_id):
        with self.lock:
            return [m for m in self.recentes if m["id"] > ultimo_id]
