"""
Benchmark HTTP — mede as métricas do trabalho
=============================================

Dispara N requisições contra a API e coleta, de forma reprodutível, as MESMAS
métricas usadas na *Avaliação Comparativa de Protocolos de Comunicação em IoT*:

  * Tempo de Resposta (ms)  -> latência request->response (média e p95)
  * Volume de Dados (bytes) -> cabeçalhos + corpo, somando envio e recepção
  * Taxa de Sucesso (%)     -> respostas 2xx sobre o total

Além disso, roda o benchmark em DOIS cenários e mostra os números lado a lado:

  * keep-alive        -> uma única `requests.Session` reaproveita a conexão TCP
  * conexão por req.  -> uma conexão nova a cada requisição (Connection: close)

Esse é exatamente o ponto que a apresentação levanta sobre o custo de rede do
HTTP: aqui ele deixa de ser argumento e vira número para o relatório.

Uso (com o servidor no ar):
    uvicorn src.servidor:app            # noutro terminal
    python scripts/benchmark.py --n 200
    python scripts/benchmark.py --n 500 --url http://localhost:8000
"""
import argparse
import os
import statistics
import sys
import time

# permite importar os módulos de src/ mesmo rodando a partir de scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import requests  # noqa: E402

import config  # noqa: E402

ID_BENCH = "BENCH-001"


def _corpo_localizacao(i: int) -> dict:
    """Payload realista de localização (varia levemente a cada iteração)."""
    return {
        "latitude": round(config.ORIGEM_LAT + i * 1e-5, 6),
        "longitude": round(config.ORIGEM_LON + i * 1e-5, 6),
        "velocidade_kmh": 22.5,
        "bateria": 90,
    }


def _bytes_transacao(resp: requests.Response) -> int:
    """
    Aproxima os bytes trafegados numa transação (envio + recepção): linha de
    request, cabeçalhos e corpo de ambos os lados. Não é o total exato do fio
    (não conta framing de TCP/TLS), mas é consistente entre os cenários e serve
    para comparar o overhead relativo do HTTP.
    """
    req = resp.request
    enviados = len(req.method or "") + len(req.url or "")
    enviados += sum(len(k) + len(str(v)) + 4 for k, v in req.headers.items())
    if req.body:
        enviados += len(req.body if isinstance(req.body, bytes) else req.body.encode())

    recebidos = sum(len(k) + len(str(v)) + 4 for k, v in resp.headers.items())
    recebidos += len(resp.content)
    return enviados + recebidos


def _percentil(valores: list[float], p: float) -> float:
    """p-ésimo percentil (0..100) por interpolação linear. Lista não vazia."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    pos = (p / 100) * (len(ordenados) - 1)
    baixo = int(pos)
    frac = pos - baixo
    if baixo + 1 >= len(ordenados):
        return ordenados[-1]
    return ordenados[baixo] + frac * (ordenados[baixo + 1] - ordenados[baixo])


def rodar_cenario(nome: str, n: int, url_base: str, keep_alive: bool) -> dict:
    """Executa N POSTs de localização e devolve as métricas agregadas."""
    url = f"{url_base}/entregadores/{ID_BENCH}/localizacao"
    print(f"  cenário '{nome}': {n} requisições...", flush=True)

    sessao = requests.Session()
    if keep_alive:
        sessao.headers.update({"Content-Type": "application/json"})
    else:
        # Connection: close força o servidor a encerrar a conexão -> nova
        # conexão TCP na próxima requisição, sem reaproveitamento.
        sessao.headers.update({"Content-Type": "application/json", "Connection": "close"})

    latencias: list[float] = []
    sucessos = 0
    erros = 0
    total_bytes = 0

    for i in range(n):
        corpo = _corpo_localizacao(i)
        t0 = time.perf_counter()
        try:
            r = sessao.post(url, json=corpo, timeout=config.TIMEOUT)
        except requests.RequestException:
            erros += 1
            continue
        latencias.append((time.perf_counter() - t0) * 1000.0)  # ms
        if 200 <= r.status_code < 300:
            sucessos += 1
        total_bytes += _bytes_transacao(r)

    sessao.close()

    respondidas = len(latencias)
    return {
        "nome": nome,
        "n": n,
        "respondidas": respondidas,
        "erros": erros,
        "sucessos": sucessos,
        "taxa_sucesso": (100.0 * sucessos / n) if n else 0.0,
        "lat_media": statistics.fmean(latencias) if latencias else 0.0,
        "lat_p95": _percentil(latencias, 95),
        "bytes_por_req": (total_bytes / respondidas) if respondidas else 0.0,
        "total_bytes": total_bytes,
    }


def imprimir_resultados(resultados: list[dict]) -> None:
    print()
    print("=" * 74)
    print("  BENCHMARK HTTP — métricas do trabalho (rastreamento de entregas)")
    print("=" * 74)
    cab = f"{'CENÁRIO':<22}{'LAT MÉDIA':>11}{'LAT p95':>10}{'SUCESSO':>10}{'BYTES/REQ':>12}"
    print(cab)
    print("-" * 74)
    for r in resultados:
        print(
            f"{r['nome']:<22}"
            f"{r['lat_media']:>9.2f}ms"
            f"{r['lat_p95']:>8.2f}ms"
            f"{r['taxa_sucesso']:>9.1f}%"
            f"{r['bytes_por_req']:>12.0f}"
        )
    print("-" * 74)

    # comparação keep-alive vs conexão nova, quando ambos rodaram
    por_nome = {r["nome"]: r for r in resultados}
    ka, nova = por_nome.get("keep-alive"), por_nome.get("conexão por req.")
    if ka and nova and ka["lat_media"]:
        delta = 100.0 * (nova["lat_media"] - ka["lat_media"]) / ka["lat_media"]
        print(f"  Abrir conexão nova a cada requisição custou "
              f"{delta:+.1f}% de latência média vs. keep-alive.")
    total_erros = sum(r["erros"] for r in resultados)
    if total_erros:
        print(f"  Atenção: {total_erros} requisição(ões) falharam (erro de rede/timeout).")
    print("  (Volume de dados é aproximado: cabeçalhos + corpo, envio + recepção.)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark HTTP da API de entregas")
    parser.add_argument("--n", type=int, default=50,
                        help="Número de requisições por cenário")
    parser.add_argument("--url", default=config.BASE_URL,
                        help="URL base da API (default: config.BASE_URL)")
    args = parser.parse_args()

    print(f"Rodando {args.n} requisições/cenário contra {args.url} ...", flush=True)
    resultados = [
        rodar_cenario("keep-alive", args.n, args.url, keep_alive=True),
        rodar_cenario("conexão por req.", args.n, args.url, keep_alive=False),
    ]

    if all(r["respondidas"] == 0 for r in resultados):
        print(f"\nNenhuma requisição obteve resposta. O servidor está no ar em {args.url}?")
        print("Suba com:  uvicorn src.servidor:app")
        sys.exit(1)

    imprimir_resultados(resultados)


if __name__ == "__main__":
    main()
