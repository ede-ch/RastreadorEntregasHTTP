# Arquitetura

## Visão geral

O sistema segue o modelo **cliente-servidor** clássico do HTTP, com três papéis:

1. **Servidor (API REST)** — `src/servidor.py`. Componente passivo. Recebe dados
   dos entregadores e responde consultas. Mantém o estado da frota em memória.
2. **Entregadores (clientes produtores)** — `src/entregador.py`. Cada um simula
   um entregador móvel que envia localização e status.
3. **Central (cliente consumidor)** — `src/central.py`. Consulta a frota por
   *polling* e exibe um painel ao vivo.

```
                         ┌───────────────────────────────────┐
                         │            SERVIDOR                │
                         │            (FastAPI)               │
   POST /loc  ──────────▶│  receber_localizacao()             │
   PUT  /status ────────▶│  atualizar_status()                │
                         │                                    │
                         │     frota: dict[id, EntregadorInfo]│
                         │                                    │
   GET /entregadores ◀───│  listar_frota()                    │
                         └───────────────────────────────────┘
        ▲                          ▲                    ▲
        │ requests.Session         │                    │ requests.get (polling)
   ┌────┴─────┐              ┌──────┴─────┐         ┌─────┴──────┐
   │ ENTG-001 │   ...        │  ENTG-NNN  │         │  CENTRAL   │
   └──────────┘              └────────────┘         └────────────┘
```

## Fluxo de uma entrega

O método `Entregador.rodar()` reproduz o ciclo de vida de uma rota:

```
DISPONIVEL
   └─▶ A_CAMINHO (recebe um pedido)
          └─▶ envia N localizações (POST) enquanto se desloca
                 └─▶ ENTREGUE (incrementa contador)
                        └─▶ RETORNANDO
                               └─▶ (volta para A_CAMINHO com novo pedido)
```

Ao encerrar (Ctrl+C), publica `OFFLINE`.

## Decisões de projeto

### Por que FastAPI no servidor
- Validação automática do corpo das requisições via Pydantic → respostas `422`
  bem formadas quando o JSON foge ao contrato, sem código manual.
- Documentação OpenAPI/Swagger gratuita em `/docs`, útil para inspeção e testes.
- Tipagem explícita, que ajuda a entender o contrato de cada rota.

### Por que `requests.Session` no cliente
Sem `Session`, cada `POST`/`PUT` abriria uma nova conexão TCP (handshake +
*slow start* a cada mensagem). Com `Session`, a conexão é reaproveitada
(keep-alive). Isso é relevante porque o trabalho aponta o custo de rede do HTTP
como sua principal desvantagem em IoT — e o `Session` é a forma justa de medir.

### Por que a central faz *polling*
O HTTP é estritamente requisição/resposta: o servidor **não** consegue iniciar
uma comunicação para avisar a central de uma mudança. A única saída é a central
perguntar de tempos em tempos (`GET /entregadores`). Isso gera tráfego mesmo
quando nada mudou — o oposto do *publish/subscribe* do MQTT, onde o broker
empurra a mensagem assim que ela chega. É o ponto de comparação mais importante
do projeto.

### Estado em memória
A frota é um `dict` em memória, suficiente para a simulação. Em um sistema real,
seria um banco (PostgreSQL, Redis) — substituível sem alterar as rotas.

## Limitações conhecidas

- Sem persistência: reiniciar o servidor zera a frota.
- Sem autenticação/TLS (ver "Trabalhos futuros" no README).
- `OFFLINE` depende de um encerramento educado do cliente; uma queda abrupta
  deixa o último estado "preso" (no MQTT, o *Last Will* resolveria isso
  automaticamente — outra diferença interessante para o relatório).
