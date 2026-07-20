"""
Entregador (Cliente HTTP)
=========================

Simula um entregador percorrendo a cidade. A cada ciclo envia para a API:
  - localização, via  POST /entregadores/{id}/localizacao
  - status,      via  PUT  /entregadores/{id}/status

Detalhe importante (e ligado direto à apresentação): usamos `requests.Session`.

  Sem Session, cada requisição abriria uma NOVA conexão TCP — justamente o
  "alto consumo de rede/CPU" que a apresentação aponta como ponto fraco do HTTP.
  Com Session, a biblioteca mantém a conexão viva (keep-alive) e reaproveita o
  socket entre requisições, reduzindo bastante esse custo. É a forma "honesta"
  de medir o HTTP, e dá pra discutir os dois modos no relatório.

Uso:
    python src/entregador.py --id ENTG-001
    python src/entregador.py --id ENTG-002 --intervalo 1
"""
import argparse
import random
import signal
import threading
import time

import requests

import config
from modelos import EstadoEntrega


class Entregador:
    def __init__(self, id_entregador: str, intervalo: float = config.INTERVALO_PADRAO):
        self.id = id_entregador
        self.intervalo = intervalo

        self.lat = config.ORIGEM_LAT + random.uniform(-0.02, 0.02)
        self.lon = config.ORIGEM_LON + random.uniform(-0.02, 0.02)
        self.bateria = 100
        self.entregas_concluidas = 0
        self._rodando = True

        # Session com keep-alive (reuso de conexão TCP) + retry com backoff:
        # se uma requisição falhar (timeout, 503...), a própria Session tenta de
        # novo com espera crescente antes de propagar o erro. Ver config.nova_sessao().
        self.sessao = config.nova_sessao()

    # ----- requisições ----------------------------------------------------
    def _post_localizacao(self):
        self.lat += random.uniform(-0.001, 0.001)
        self.lon += random.uniform(-0.001, 0.001)
        self.bateria = max(0, self.bateria - random.randint(0, 1))

        corpo = {
            "latitude": round(self.lat, 6),
            "longitude": round(self.lon, 6),
            "velocidade_kmh": round(random.uniform(0, 45), 1),
            "bateria": self.bateria,
        }
        try:
            r = self.sessao.post(
                config.url_localizacao(self.id), json=corpo, timeout=config.TIMEOUT
            )
            # diferente do MQTT, cada requisição tem um código de resposta próprio
            if r.status_code != 201:
                print(f"[{self.id}] localização rejeitada: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"[{self.id}] erro de rede ao enviar localização: {e}")

    def _put_status(self, estado: EstadoEntrega, pedido: str | None = None):
        corpo = {
            "estado": estado.value,
            "pedido_atual": pedido,
            "entregas_concluidas": self.entregas_concluidas,
        }
        try:
            r = self.sessao.put(
                config.url_status(self.id), json=corpo, timeout=config.TIMEOUT
            )
            if r.status_code == 200:
                print(f"[{self.id}] status -> {estado.value}"
                      + (f" (pedido {pedido})" if pedido else ""))
            else:
                print(f"[{self.id}] status rejeitado: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"[{self.id}] erro de rede ao enviar status: {e}")

    # ----- ciclo de vida --------------------------------------------------
    def rodar(self):
        # signal.signal() só pode ser chamado na thread principal. Quando o
        # entregador roda dentro de uma thread (simulador de frota), quem cuida
        # do encerramento é o próprio simulador, via _parar().
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._parar)
            signal.signal(signal.SIGTERM, self._parar)

        self._put_status(EstadoEntrega.DISPONIVEL)

        pedido_id = 1
        while self._rodando:
            pedido = f"PED-{self.id[-3:]}{pedido_id:03d}"
            self._put_status(EstadoEntrega.A_CAMINHO, pedido)

            for _ in range(random.randint(4, 8)):
                if not self._rodando:
                    break
                self._post_localizacao()
                time.sleep(self.intervalo)

            if not self._rodando:
                break

            self.entregas_concluidas += 1
            self._put_status(EstadoEntrega.ENTREGUE, pedido)
            time.sleep(self.intervalo)

            self._put_status(EstadoEntrega.RETORNANDO)
            time.sleep(self.intervalo)
            pedido_id += 1

        self._encerrar()

    def _parar(self, *args):
        self._rodando = False

    def _encerrar(self):
        self._put_status(EstadoEntrega.OFFLINE)
        self.sessao.close()
        print(f"[{self.id}] encerrado. Entregas concluídas: {self.entregas_concluidas}")


def main():
    parser = argparse.ArgumentParser(description="Simulador de entregador (cliente HTTP)")
    parser.add_argument("--id", default="ENTG-001", help="Identificador do entregador")
    parser.add_argument("--intervalo", type=float, default=config.INTERVALO_PADRAO,
                        help="Segundos entre envios de localização")
    args = parser.parse_args()

    Entregador(args.id, args.intervalo).rodar()


if __name__ == "__main__":
    main()
