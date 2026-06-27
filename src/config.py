"""
Configurações centrais do sistema de rastreamento de entregas via HTTP.

Centralizar tudo aqui evita "valores mágicos" espalhados pelo código e permite
apontar para outro servidor (local <-> remoto) sem mexer na lógica.
Todos os valores podem ser sobrescritos por variáveis de ambiente.
"""
import os

# ---------------------------------------------------------------------------
# Servidor / API
# ---------------------------------------------------------------------------
# URL base que os CLIENTES (entregadores e central) usam para falar com a API.
BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# Endereço/porta em que o SERVIDOR escuta.
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8000"))

# Timeout de cada requisição HTTP (segundos). Diferente do MQTT, no HTTP cada
# mensagem é uma requisição independente que pode falhar isoladamente.
TIMEOUT = 5.0

# ---------------------------------------------------------------------------
# Endpoints (rotas REST)
# ---------------------------------------------------------------------------
#   POST  /entregadores/{id}/localizacao   -> envia um ponto de GPS
#   PUT   /entregadores/{id}/status        -> atualiza o status da entrega
#   GET   /entregadores                    -> lista a frota inteira
#   GET   /entregadores/{id}               -> detalhe de um entregador


def url_localizacao(id_entregador: str) -> str:
    return f"{BASE_URL}/entregadores/{id_entregador}/localizacao"


def url_status(id_entregador: str) -> str:
    return f"{BASE_URL}/entregadores/{id_entregador}/status"


def url_entregador(id_entregador: str) -> str:
    return f"{BASE_URL}/entregadores/{id_entregador}"


URL_FROTA = f"{BASE_URL}/entregadores"

# ---------------------------------------------------------------------------
# Simulação
# ---------------------------------------------------------------------------
# A apresentação usou 10s entre mensagens. Para a demo isso é lento demais,
# então deixamos um valor menor por padrão — ajustável via parâmetro.
INTERVALO_PADRAO = 2.0  # segundos entre envios de localização

# A central, por não ter "push" no HTTP, precisa CONSULTAR (polling) de tempos
# em tempos. Este é o intervalo entre cada consulta.
INTERVALO_POLLING = 2.0

# Ponto de partida geográfico: Alegrete/RS (sede da UNIPAMPA).
ORIGEM_LAT = -29.7833
ORIGEM_LON = -55.7917
