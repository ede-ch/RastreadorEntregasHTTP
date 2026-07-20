# Rastreamento de Entregas via HTTP

Implementação de referência do protocolo **HTTP** para um cenário de **IoT móvel — rastreamento de entregas em tempo real**, desenvolvida como complemento prático para Atividades Interativas, juntamente com o trabalho: *Avaliação Comparativa de Protocolos de Comunicação em IoT (MQTT, HTTP e CoAP)* da disciplina de Redes de Computadores (UNIPAMPA). 

Uma frota de entregadores envia continuamente sua **localização** e **status** para uma **API REST** central. Qualquer consumidor (a central de monitoramento) consulta a frota inteira via HTTP.

> Protocolo escolhido: **HTTP**, no padrão requisição/resposta cliente-servidor, com `FastAPI` no servidor e `requests` no cliente — exatamente a biblioteca usada na metodologia do trabalho.

---

## Arquitetura

```
   ENTREGADORES (clientes)                 SERVIDOR (API REST)          CENTRAL (cliente)
  ┌────────────────────┐                ┌─────────────────────┐      ┌──────────────────┐
  │  entregador.py      │  POST /loc     │   servidor.py        │      │   central.py     │
  │  (requests.Session) │ ─────────────▶ │   (FastAPI)          │ ◀─── │   GET /entreg.   │
  │  ENTG-001           │  PUT  /status  │                      │ polling   (a cada 2s)  │
  │  ENTG-002    ...    │ ─────────────▶ │  frota = {} (memória)│      │   redesenha tela │
  └────────────────────┘                └─────────────────────┘      └──────────────────┘
```

Detalhes em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

---

## Como rodar

Pré-requisitos: Python 3.10+.

```bash
# 1. instalar dependências
pip install -r requirements.txt

# 2. subir o servidor (API REST) — deixe rodando neste terminal
uvicorn src.servidor:app --reload
#   Swagger interativo em:  http://localhost:8000/docs

# 3. em outro terminal, subir um entregador
python src/entregador.py --id ENTG-001

# 4. em outro terminal, abrir a central de monitoramento (painel ao vivo)
python src/central.py
```

### Simulando uma frota (cenários de carga do trabalho: 1, 10, 50)

```bash
python scripts/simular_frota.py --n 10        # 10 entregadores simultâneos
python scripts/simular_frota.py --n 50 --intervalo 1
```

### Medindo as métricas do trabalho (benchmark)

Com o servidor no ar, o script abaixo dispara N requisições e imprime **tempo de
resposta (média/p95)**, **volume de dados por requisição** e **taxa de sucesso** —
comparando ainda **keep-alive** vs. **uma conexão nova por requisição**:

```bash
python scripts/benchmark.py --n 50
python scripts/benchmark.py --n 200 --url http://localhost:8000
```

### Testando resiliência (servidor instável)

Os clientes (entregador e central) usam uma `Session` com **retry + backoff
exponencial**. Para exercitar isso, suba o servidor em modo instável via
variáveis de ambiente — sem elas, o comportamento é o normal:

```bash
# ~30% das requisições respondem 503, com 800ms de latência artificial
FALHA_PCT=30 FALHA_LATENCIA_MS=800 uvicorn src.servidor:app
```

Com o servidor assim, um entregador continua entregando (reenviando as
requisições que falham) em vez de desistir na primeira falha.

### Usando Docker para o servidor

```bash
docker compose up --build      # sobe a API em http://localhost:8000
```

---

## Endpoints da API

| Método | Rota                                   | Descrição                              | Status |
|--------|----------------------------------------|----------------------------------------|--------|
| `GET`  | `/healthz`                             | Health check                           | 200    |
| `POST` | `/entregadores/{id}/localizacao`       | Envia um ponto de GPS                   | 201    |
| `PUT`  | `/entregadores/{id}/status`            | Atualiza o status da entrega            | 200    |
| `GET`  | `/entregadores`                        | Lista a frota inteira                   | 200    |
| `GET`  | `/entregadores/{id}`                   | Detalhe de um entregador                | 200/404|

Exemplo de envio de localização:

```bash
curl -X POST http://localhost:8000/entregadores/ENTG-001/localizacao \
  -H "Content-Type: application/json" \
  -d '{"latitude":-29.783,"longitude":-55.791,"velocidade_kmh":22.5,"bateria":95}'
```

---

## Conceitos de HTTP demonstrados

O código foi escrito para evidenciar as características do HTTP discutidas no trabalho:

- **Requisição/Resposta:** cada mensagem é uma transação independente; o servidor é passivo e só responde quando perguntado.
- **Métodos com semântica correta:** `POST` cria, `PUT` atualiza, `GET` consulta sem efeitos colaterais.
- **Códigos de status:** `201 Created`, `200 OK`, `404 Not Found` e `422` (validação automática do Pydantic quando o JSON foge ao contrato).
- **Conexão por requisição vs. keep-alive:** o cliente usa `requests.Session`, que reaproveita a conexão TCP. Esse é o ponto exato que a apresentação levanta sobre o custo de rede do HTTP — dá para discutir, no relatório, o impacto de abrir uma nova conexão a cada mensagem.
- **Ausência de push → polling:** como o HTTP não empurra dados, a central precisa *consultar* periodicamente, gerando tráfego mesmo quando nada muda. É o contraste central com o modelo publish/subscribe do MQTT.

---

## Relação com as métricas do trabalho

| Métrica do trabalho      | Onde aparece neste projeto                                           |
|--------------------------|---------------------------------------------------------------------|
| Tempo de Resposta (ms)   | latência da chamada `requests` (request → response)                 |
| Volume de Dados (KB)     | cabeçalhos HTTP + corpo JSON por requisição                          |
| Taxa de Sucesso (%)      | proporção de respostas `2xx` sobre o total de requisições            |
| Uso de CPU / Memória     | custo de manter o servidor + abrir/manter conexões                  |

---

## Estrutura do projeto

```
http-rastreamento-entregas/
├── src/
│   ├── config.py          # URLs, endpoints, timeouts, retry, fábrica de Session
│   ├── modelos.py         # modelos Pydantic (contrato das mensagens)
│   ├── servidor.py        # API REST (FastAPI) + modo instável (FALHA_PCT)
│   ├── entregador.py      # cliente: simula um entregador (requests)
│   └── central.py         # cliente: painel de monitoramento (polling)
├── scripts/
│   ├── simular_frota.py   # sobe N entregadores simultâneos
│   └── benchmark.py       # mede latência, volume e taxa de sucesso
├── docs/
│   └── ARQUITETURA.md
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Trabalhos futuros

Alinhado às propostas da apresentação:

- Adicionar **HTTPS/TLS** e autenticação (token) para medir o custo da segurança.
- ~~Comparar **conexão por requisição vs. keep-alive** com números.~~ ✅ `scripts/benchmark.py`
- ~~Testar **resiliência** com o servidor instável (timeouts, retry, *backoff*).~~ ✅ `FALHA_PCT` + retry nos clientes

---

## Autor

Edelin Chaves dos Santos — Engenharia de Software, UNIPAMPA