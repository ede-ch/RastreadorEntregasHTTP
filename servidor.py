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
import os
import sys

# Garante que os módulos locais (modelos, config) sejam encontrados tanto ao
# rodar de dentro de src/ (uvicorn servidor:app) quanto da raiz do projeto
# (uvicorn src.servidor:app).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, status

from modelos import EntregadorInfo, EstadoEntrega, Localizacao, Status

app = FastAPI(
    title="API de Rastreamento de Entregas",
    description="Central de monitoramento de uma frota de entregadores via HTTP.",
    version="1.0.0",
)

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
