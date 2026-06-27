"""
Modelos de dados (payloads) trocados via HTTP, em JSON.

Usamos Pydantic porque é o padrão do FastAPI: o mesmo modelo serve para
  (a) validar automaticamente o corpo das requisições no servidor e
  (b) documentar a API no Swagger (/docs).
Tanto o servidor quanto o cliente importam daqui — o formato da mensagem fica
definido num lugar só.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _agora() -> str:
    """Timestamp ISO 8601 com precisão de segundos."""
    return datetime.now().isoformat(timespec="seconds")


class EstadoEntrega(str, Enum):
    """Estados possíveis de um entregador na operação."""
    DISPONIVEL = "DISPONIVEL"
    A_CAMINHO = "A_CAMINHO"
    ENTREGUE = "ENTREGUE"
    RETORNANDO = "RETORNANDO"
    OFFLINE = "OFFLINE"


class Localizacao(BaseModel):
    """Corpo do POST de localização. O id do entregador vem na URL, não aqui."""
    latitude: float
    longitude: float
    velocidade_kmh: float = Field(ge=0)
    bateria: int = Field(ge=0, le=100)
    timestamp: str = Field(default_factory=_agora)


class Status(BaseModel):
    """Corpo do PUT de status."""
    estado: EstadoEntrega
    pedido_atual: Optional[str] = None
    entregas_concluidas: int = 0
    timestamp: str = Field(default_factory=_agora)


class EntregadorInfo(BaseModel):
    """Visão consolidada de um entregador, retornada pelos GETs da frota."""
    id_entregador: str
    estado: Optional[EstadoEntrega] = None
    pedido_atual: Optional[str] = None
    entregas_concluidas: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    velocidade_kmh: Optional[float] = None
    bateria: Optional[int] = None
    ultima_atualizacao: Optional[str] = None
