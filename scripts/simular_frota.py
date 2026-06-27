"""
Simulador de Frota
==================

Sobe N entregadores ao mesmo tempo (1, 10, 50...), reproduzindo os cenários de
carga usados na avaliação de desempenho da apresentação. Cada entregador roda
na própria thread, todos batendo na mesma API.

Uso:
    python scripts/simular_frota.py --n 10
    python scripts/simular_frota.py --n 50 --intervalo 1
"""
import argparse
import os
import sys
import threading
import time

# permite importar os módulos de src/ mesmo rodando a partir de scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config                       # noqa: E402
from entregador import Entregador   # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Sobe uma frota de entregadores (HTTP)")
    parser.add_argument("--n", type=int, default=10, help="Quantidade de entregadores")
    parser.add_argument("--intervalo", type=float, default=config.INTERVALO_PADRAO,
                        help="Segundos entre envios de localização")
    args = parser.parse_args()

    print(f"Iniciando frota com {args.n} entregadores contra {config.BASE_URL}")
    print("Abra a central em outro terminal:  python src/central.py")
    print("(Ctrl+C para encerrar toda a frota)\n")

    entregadores, threads = [], []
    for i in range(1, args.n + 1):
        ent = Entregador(f"ENTG-{i:03d}", args.intervalo)
        entregadores.append(ent)
        t = threading.Thread(target=ent.rodar, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.05)  # escalona as conexões para não estourar o servidor

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nEncerrando frota...")
        for ent in entregadores:
            ent._parar()
        for t in threads:
            t.join(timeout=3)
        print("Frota encerrada.")


if __name__ == "__main__":
    main()
