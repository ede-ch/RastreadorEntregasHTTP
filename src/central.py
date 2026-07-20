"""
Central de Monitoramento (Cliente HTTP — Polling)
=================================================

No HTTP não existe "push": o servidor não consegue avisar a central quando algo
muda. Então a central faz POLLING — consulta `GET /entregadores` de tempos em
tempos e redesenha o painel.

Esse é, na prática, o grande contraste com o MQTT (onde o broker empurra as
mensagens assim que chegam). Vale destacar isso no relatório: o polling gera
requisições mesmo quando NADA mudou, desperdiçando rede — outro motivo de o HTTP
consumir mais recursos no cenário de IoT.

Uso:
    python src/central.py
"""
import os
import time

import requests

import config


def desenhar_painel(frota: list[dict]):
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 86)
    print("  CENTRAL DE MONITORAMENTO DE ENTREGAS — via HTTP (polling)")
    print("=" * 86)
    print(f"{'ENTREGADOR':<12}{'ESTADO':<12}{'PEDIDO':<12}"
          f"{'POSIÇÃO (lat, lon)':<26}{'VEL':>6}{'BAT':>5}{'OK':>5}")
    print("-" * 86)

    for d in sorted(frota, key=lambda x: x["id_entregador"]):
        estado = d.get("estado") or "—"
        pedido = d.get("pedido_atual") or "—"
        if d.get("latitude") is not None:
            pos = f"{d['latitude']:.5f}, {d['longitude']:.5f}"
            vel = f"{d.get('velocidade_kmh') or 0:.0f}"
            bat = f"{d.get('bateria') or 0}%"
        else:
            pos, vel, bat = "—", "—", "—"
        ok = d.get("entregas_concluidas", 0)
        print(f"{d['id_entregador']:<12}{estado:<12}{pedido:<12}"
              f"{pos:<26}{vel:>6}{bat:>5}{ok:>5}")

    print("-" * 86)
    ativos = sum(1 for d in frota if d.get("estado") not in (None, "OFFLINE"))
    print(f"  Entregadores na frota: {len(frota)}  |  ativos: {ativos}")
    print("  (Ctrl+C para sair)")


def main():
    print(f"Central consultando {config.URL_FROTA} a cada "
          f"{config.INTERVALO_POLLING}s...")
    # Session com retry+backoff: uma instabilidade pontual do servidor não
    # derruba o painel — a própria Session reenvia a consulta antes de desistir.
    sessao = config.nova_sessao()
    try:
        while True:
            try:
                r = sessao.get(config.URL_FROTA, timeout=config.TIMEOUT)
                r.raise_for_status()
                desenhar_painel(r.json())
            except requests.RequestException as e:
                print(f"Servidor indisponível: {e}. Tentando de novo...")
            time.sleep(config.INTERVALO_POLLING)
    except KeyboardInterrupt:
        print("\nEncerrando central...")
    finally:
        sessao.close()


if __name__ == "__main__":
    main()
