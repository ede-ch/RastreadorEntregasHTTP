"""
Servidor (API REST)
===================

A "central" no modelo HTTP é um servidor que expõe endpoints REST. Os
entregadores enviam dados via POST/PUT; qualquer consumidor lê a frota via GET.

Conceitos de HTTP demonstrados aqui (relevantes para a disciplina de Redes):

  * Métodos HTTP com semântica correta:
      POST -> cria um recurso (novo ponto de localização)        -> 201 Created
      PUT  -> atualiza/substitui o estado de um recurso          -> 200 OK
      GET  -> consulta, sem efeitos colaterais (idempotente)     -> 200 OK

  * Códigos de status: 200, 201, 404 (não encontrado), 422 (validação falhou,
    gerado automaticamente pelo Pydantic quando o JSON está fora do contrato).

  * Modelo requisição/resposta: o servidor é PASSIVO. Ele nunca "empurra" dados;
    só responde quando alguém pergunta. Por isso a central precisa fazer polling.

  * Documentação automática (OpenAPI/Swagger) em  http://localhost:8000/docs

Como rodar:
    uvicorn servidor:app --reload          (de dentro de src/)
    # ou, da raiz do projeto:
    uvicorn src.servidor:app --reload
"""
import asyncio
import os
import random
import sys

# Garante que os módulos locais (modelos, config) sejam encontrados tanto ao
# rodar de dentro de src/ (uvicorn servidor:app) quanto da raiz do projeto
# (uvicorn src.servidor:app).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from modelos import EntregadorInfo, EstadoEntrega, Localizacao, Status

app = FastAPI(
    title="API de Rastreamento de Entregas",
    description="Central de monitoramento de uma frota de entregadores via HTTP.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Modo "servidor instável" (opcional, para testar resiliência do cliente)
# ---------------------------------------------------------------------------
# Sem variáveis de ambiente o servidor se comporta normalmente. Definindo:
#   FALHA_PCT=30            -> ~30% das requisições respondem 503
#   FALHA_LATENCIA_MS=800   -> adiciona 800ms de latência antes de responder
# dá para observar, na prática, o retry+backoff dos clientes reagindo a um
# servidor ruim — justamente o item "resiliência" dos trabalhos futuros.
FALHA_PCT = float(os.getenv("FALHA_PCT", "0"))
FALHA_LATENCIA_MS = float(os.getenv("FALHA_LATENCIA_MS", "0"))


@app.middleware("http")
async def instabilidade(request: Request, call_next):
    # /healthz nunca é sabotado: a central o usa para saber se o servidor vive.
    if request.url.path != "/healthz" and (FALHA_PCT > 0 or FALHA_LATENCIA_MS > 0):
        if FALHA_LATENCIA_MS > 0:
            await asyncio.sleep(FALHA_LATENCIA_MS / 1000.0)
        if FALHA_PCT > 0 and random.random() < FALHA_PCT / 100.0:
            return JSONResponse(
                status_code=503,
                content={"detail": "instabilidade simulada (FALHA_PCT)"},
            )
    return await call_next(request)

# "Banco de dados" em memória. Em produção isto seria Postgres, Redis, etc.
frota: dict[str, EntregadorInfo] = {}


def _obter_ou_criar(id_entregador: str) -> EntregadorInfo:
    if id_entregador not in frota:
        frota[id_entregador] = EntregadorInfo(id_entregador=id_entregador)
    return frota[id_entregador]


@app.get("/healthz", tags=["infra"])
def health():
    """Health check — usado por load balancers e pela própria central."""
    return {"status": "ok", "entregadores": len(frota)}


@app.post(
    "/entregadores/{id_entregador}/localizacao",
    status_code=status.HTTP_201_CREATED,
    tags=["entregador"],
)
def receber_localizacao(id_entregador: str, loc: Localizacao):
    """Recebe um ponto de GPS de um entregador (uma requisição por ponto)."""
    info = _obter_ou_criar(id_entregador)
    info.latitude = loc.latitude
    info.longitude = loc.longitude
    info.velocidade_kmh = loc.velocidade_kmh
    info.bateria = loc.bateria
    info.ultima_atualizacao = loc.timestamp
    return {"recebido": True, "id_entregador": id_entregador}


@app.put(
    "/entregadores/{id_entregador}/status",
    response_model=EntregadorInfo,
    tags=["entregador"],
)
def atualizar_status(id_entregador: str, st: Status):
    """Atualiza o status da entrega (DISPONIVEL, A_CAMINHO, ENTREGUE...)."""
    info = _obter_ou_criar(id_entregador)
    info.estado = st.estado
    info.pedido_atual = st.pedido_atual
    info.entregas_concluidas = st.entregas_concluidas
    info.ultima_atualizacao = st.timestamp
    return info


@app.get("/entregadores", response_model=list[EntregadorInfo], tags=["frota"])
def listar_frota():
    """Lista toda a frota com o último estado conhecido de cada entregador."""
    return list(frota.values())


@app.get("/entregadores/{id_entregador}", response_model=EntregadorInfo, tags=["frota"])
def detalhe_entregador(id_entregador: str):
    """Detalhe de um entregador específico."""
    if id_entregador not in frota:
        raise HTTPException(status_code=404, detail="Entregador não encontrado")
    return frota[id_entregador]
