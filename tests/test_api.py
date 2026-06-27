"""
Testes automatizados da API REST de rastreamento de entregas.

Usa FastAPI TestClient (in-process) — não precisa de servidor externo rodando.
Cada teste é independente graças ao fixture `app_limpo` que reseta a frota.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from fastapi.testclient import TestClient

from servidor import app, frota

LOC_VALIDA = {
    "latitude": -29.783,
    "longitude": -55.791,
    "velocidade_kmh": 22.5,
    "bateria": 95,
}


@pytest.fixture(autouse=True)
def limpar_frota():
    """Reseta o estado em memória antes de cada teste."""
    frota.clear()
    yield
    frota.clear()


client = TestClient(app)


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------

def test_healthz_retorna_200():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["entregadores"] == 0


def test_healthz_conta_entregadores():
    client.post("/entregadores/ENTG-T01/localizacao", json=LOC_VALIDA)
    r = client.get("/healthz")
    assert r.json()["entregadores"] == 1


# ---------------------------------------------------------------------------
# POST /entregadores/{id}/localizacao
# ---------------------------------------------------------------------------

def test_post_localizacao_retorna_201():
    r = client.post("/entregadores/ENTG-001/localizacao", json=LOC_VALIDA)
    assert r.status_code == 201
    assert r.json()["recebido"] is True
    assert r.json()["id_entregador"] == "ENTG-001"


def test_post_localizacao_persiste_dados():
    client.post("/entregadores/ENTG-001/localizacao", json=LOC_VALIDA)
    r = client.get("/entregadores/ENTG-001")
    body = r.json()
    assert body["latitude"] == LOC_VALIDA["latitude"]
    assert body["longitude"] == LOC_VALIDA["longitude"]
    assert body["velocidade_kmh"] == LOC_VALIDA["velocidade_kmh"]
    assert body["bateria"] == LOC_VALIDA["bateria"]


def test_post_localizacao_atualiza_posicao():
    client.post("/entregadores/ENTG-001/localizacao", json=LOC_VALIDA)
    nova = {**LOC_VALIDA, "latitude": -29.800, "longitude": -55.810}
    client.post("/entregadores/ENTG-001/localizacao", json=nova)
    r = client.get("/entregadores/ENTG-001")
    assert r.json()["latitude"] == -29.800


def test_post_localizacao_bateria_invalida_422():
    payload = {**LOC_VALIDA, "bateria": 200}  # bateria > 100
    r = client.post("/entregadores/ENTG-001/localizacao", json=payload)
    assert r.status_code == 422


def test_post_localizacao_velocidade_negativa_422():
    payload = {**LOC_VALIDA, "velocidade_kmh": -5}  # velocidade < 0
    r = client.post("/entregadores/ENTG-001/localizacao", json=payload)
    assert r.status_code == 422


def test_post_localizacao_campos_faltando_422():
    r = client.post("/entregadores/ENTG-001/localizacao",
                    json={"latitude": -29.783})  # falta longitude, velocidade, bateria
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# PUT /entregadores/{id}/status
# ---------------------------------------------------------------------------

def test_put_status_retorna_200():
    r = client.put("/entregadores/ENTG-001/status",
                   json={"estado": "A_CAMINHO", "pedido_atual": "PED-001",
                         "entregas_concluidas": 0})
    assert r.status_code == 200


def test_put_status_persiste_estado():
    client.put("/entregadores/ENTG-001/status",
               json={"estado": "ENTREGUE", "pedido_atual": "PED-002",
                     "entregas_concluidas": 3})
    r = client.get("/entregadores/ENTG-001")
    body = r.json()
    assert body["estado"] == "ENTREGUE"
    assert body["pedido_atual"] == "PED-002"
    assert body["entregas_concluidas"] == 3


def test_put_status_estado_invalido_422():
    r = client.put("/entregadores/ENTG-001/status",
                   json={"estado": "ESTADO_INEXISTENTE"})
    assert r.status_code == 422


def test_put_todos_os_estados_validos():
    estados = ["DISPONIVEL", "A_CAMINHO", "ENTREGUE", "RETORNANDO", "OFFLINE"]
    for estado in estados:
        r = client.put("/entregadores/ENTG-001/status", json={"estado": estado})
        assert r.status_code == 200, f"Estado {estado} deveria retornar 200"


# ---------------------------------------------------------------------------
# GET /entregadores
# ---------------------------------------------------------------------------

def test_get_frota_vazia():
    r = client.get("/entregadores")
    assert r.status_code == 200
    assert r.json() == []


def test_get_frota_lista_todos():
    client.post("/entregadores/ENTG-001/localizacao", json=LOC_VALIDA)
    client.post("/entregadores/ENTG-002/localizacao", json=LOC_VALIDA)
    r = client.get("/entregadores")
    ids = [e["id_entregador"] for e in r.json()]
    assert "ENTG-001" in ids
    assert "ENTG-002" in ids
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# GET /entregadores/{id}
# ---------------------------------------------------------------------------

def test_get_entregador_existente_200():
    client.post("/entregadores/ENTG-001/localizacao", json=LOC_VALIDA)
    r = client.get("/entregadores/ENTG-001")
    assert r.status_code == 200
    assert r.json()["id_entregador"] == "ENTG-001"


def test_get_entregador_inexistente_404():
    r = client.get("/entregadores/INEXISTENTE-XYZ")
    assert r.status_code == 404
    assert "não encontrado" in r.json()["detail"].lower() or "not found" in r.json()["detail"].lower()


def test_get_entregador_criado_por_put_status():
    # PUT em ID novo deve criá-lo (via _obter_ou_criar)
    client.put("/entregadores/ENTG-NEW/status",
               json={"estado": "DISPONIVEL", "entregas_concluidas": 0})
    r = client.get("/entregadores/ENTG-NEW")
    assert r.status_code == 200
