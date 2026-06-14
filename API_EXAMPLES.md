# 🧪 Exemplos Práticos: Usando a API com Mensagens Estruturadas

Exemplos cURL e Python mostrando como consumir a API com as novas mensagens de erro estruturadas.

---

## 1. Sucesso: Criar Reserva

### Request
```bash
curl -X POST http://localhost:8000/reservas/ \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
    "recurso_id": "650e8400-e29b-41d4-a716-446655440001",
    "data_inicio": "2024-03-15T14:00:00",
    "data_fim": "2024-03-15T16:00:00"
  }'
```

### Response (201)
```json
{
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
  "recurso_id": "650e8400-e29b-41d4-a716-446655440001",
  "data_inicio": "2024-03-15T14:00:00",
  "data_fim": "2024-03-15T16:00:00",
  "status": "SOLICITADA"
}
```

---

## 2. Erro: Usuário Suspenso (RN-002)

### Request
```bash
curl -X POST http://localhost:8000/reservas/ \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "suspended-user-id",
    "recurso_id": "resource-id",
    "data_inicio": "2024-03-15T14:00:00",
    "data_fim": "2024-03-15T16:00:00"
  }'
```

### Response (403)
```json
{
  "error": "USER_SUSPENDED",
  "message": "Sua conta possui pendências ou suspensões ativas.",
  "details": {
    "usuario_id": "suspended-user-id",
    "reason": "Pendências ou suspensões ativas",
    "rule": "RN-002"
  }
}
```

### Cliente Python: Como Tratar
```python
import requests
from typing import Dict, Any

def criar_reserva(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(f"{url}/reservas/", json=payload)
    
    if response.status_code == 403:
        error = response.json()
        if error["error"] == "USER_SUSPENDED":
            print(f"⚠️ Usuário bloqueado: {error['details']['reason']}")
            print(f"   Contate suporte para desbloquear a conta")
            return None
    
    if response.status_code == 201:
        return response.json()
    
    # Tratar outros erros...
```

---

## 3. Erro: Sobreposição de Horário (RN-001)

### Request
```bash
curl -X POST http://localhost:8000/reservas/ \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "user-id",
    "recurso_id": "resource-already-booked",
    "data_inicio": "2024-03-15T14:30:00",
    "data_fim": "2024-03-15T15:30:00"
  }'
```

### Response (409)
```json
{
  "error": "RESERVATION_CONFLICT",
  "message": "Já existe uma reserva para este recurso no período solicitado.",
  "details": {
    "conflicting_period": {
      "start": "2024-03-15T14:00:00",
      "end": "2024-03-15T16:00:00"
    },
    "recurso_id": "resource-already-booked",
    "rule": "RN-001"
  }
}
```

### Cliente Python: Sugerir Próximo Slot
```python
from datetime import datetime, timedelta

def handle_conflict(error_details):
    conflicting = error_details["conflicting_period"]
    conflict_end = datetime.fromisoformat(conflicting["end"])
    
    # Sugerir próximo slot: 30 minutos após o fim
    suggested_start = conflict_end + timedelta(minutes=30)
    suggested_end = suggested_start + timedelta(hours=2)
    
    print(f"❌ Recurso indisponível nesse período")
    print(f"   Ocupado: {conflicting['start']} até {conflicting['end']}")
    print(f"✅ Sugestão: Agende para {suggested_start.strftime('%H:%M')}")
```

---

## 4. Erro: Limite de Aluno (RN-004)

### Request
```bash
curl -X POST http://localhost:8000/reservas/ \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "aluno-xyz",
    "recurso_id": "resource-id",
    "data_inicio": "2024-03-20T14:00:00",
    "data_fim": "2024-03-20T16:00:00"
  }'
```

### Response (422)
```json
{
  "error": "STUDENT_LIMIT_EXCEEDED",
  "message": "Usuários do tipo ALUNO só podem possuir até 3 reservas ativas simultaneamente.",
  "details": {
    "usuario_id": "aluno-xyz",
    "current_active_reservations": 3,
    "limit": 3,
    "exceeding_by": 1,
    "rule": "RN-004"
  }
}
```

### Cliente Python: Listar Reservas Existentes
```python
def handle_limit_exceeded(error_details, api_url, user_id):
    print(f"❌ Limite atingido: {error_details['current_active_reservations']}/{error_details['limit']}")
    
    # Buscar reservas ativas
    response = requests.get(f"{api_url}/reservas/?limit=10&offset=0")
    reservas = response.json()["results"]
    
    print("📋 Suas reservas ativas:")
    for r in reservas:
        print(f"   - {r['data_inicio']} a {r['data_fim']} ({r['status']})")
    
    print("💡 Cancele uma reserva para criar outra")
```

---

## 5. Erro: Prazo Insuficiente para Cancelamento (RN-003)

### Request
```bash
curl -X PATCH http://localhost:8000/reservas/{reserva-id}/status \
  -H "Content-Type: application/json" \
  -d '{
    "novo_status": "CANCELADA"
  }'
```

### Response (422)
```json
{
  "error": "INSUFFICIENT_NOTICE",
  "message": "Reservas só podem ser canceladas com antecedência mínima de 1 hora(s).",
  "details": {
    "reservation_start": "2024-03-15T14:30:00",
    "current_time": "2024-03-15T13:50:00",
    "minimum_hours": 1,
    "rule": "RN-003"
  }
}
```

### Cliente Python: Calcular Tempo Restante
```python
def handle_insufficient_notice(error_details):
    start = datetime.fromisoformat(error_details["reservation_start"])
    current = datetime.fromisoformat(error_details["current_time"])
    required = error_details["minimum_hours"]
    
    time_diff = start - current
    minutes_remaining = int(time_diff.total_seconds() / 60)
    
    print(f"❌ Prazo insuficiente para cancelar")
    print(f"   Tempo restante: {minutes_remaining} minutos")
    print(f"   Mínimo requerido: {required} hora(s)")
    print(f"✅ Você poderá cancelar em {minutes_remaining - 60} minutos")
```

---

## 6. Erro: Recurso Indisponível (RN-005)

### Request
```bash
curl -X POST http://localhost:8000/reservas/ \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "user-id",
    "recurso_id": "projector-under-maintenance",
    "data_inicio": "2024-03-15T14:00:00",
    "data_fim": "2024-03-15T16:00:00"
  }'
```

### Response (400)
```json
{
  "error": "RESOURCE_UNAVAILABLE",
  "message": "O recurso solicitado encontra-se em manutenção e não pode ser reservado.",
  "details": {
    "recurso_id": "projector-under-maintenance",
    "status": "MANUTENCAO",
    "resource_name": "Projetor Sala 301",
    "rule": "RN-005"
  }
}
```

### Cliente Python: Mostrar Status
```python
def handle_unavailable(error_details):
    resource = error_details["resource_name"]
    status = error_details["status"]
    
    status_info = {
        "MANUTENCAO": "🔧 Em manutenção",
        "INATIVO": "🛑 Desativado"
    }
    
    print(f"❌ {resource}: {status_info.get(status, status)}")
    print(f"   Não pode ser reservado no momento")
```

---

## 7. Erro: Entidade Não Encontrada (404)

### Request
```bash
curl -X POST http://localhost:8000/reservas/ \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "00000000-0000-0000-0000-000000000000",
    "recurso_id": "resource-id",
    "data_inicio": "2024-03-15T14:00:00",
    "data_fim": "2024-03-15T16:00:00"
  }'
```

### Response (404)
```json
{
  "error": "ENTITY_NOT_FOUND",
  "message": "Usuário não encontrado.",
  "details": {
    "entity_type": "Usuario",
    "entity_id": "00000000-0000-0000-0000-000000000000"
  }
}
```

---

## 8. Erro: Transição Inválida (Estado Terminal)

### Request
```bash
curl -X PATCH http://localhost:8000/reservas/{reserva-concluida}/status \
  -H "Content-Type: application/json" \
  -d '{
    "novo_status": "CANCELADA"
  }'
```

### Response (400)
```json
{
  "error": "INVALID_STATE_TRANSITION",
  "message": "Não é permitido transicionar de CONCLUIDA para CANCELADA.",
  "details": {
    "entity_type": "Reserva",
    "current_state": "CONCLUIDA",
    "requested_state": "CANCELADA"
  }
}
```

---

## 9. Middleware: Tratar Todos os Erros Estruturados

```python
import logging
from typing import Callable
import requests
from enum import Enum

class ErrorHandler:
    """Centraliza tratamento de erros da API"""
    
    # Mapeamento de erro → ação/mensagem
    HANDLERS = {
        "RESERVATION_CONFLICT": "handle_conflict",
        "USER_SUSPENDED": "handle_suspended",
        "INSUFFICIENT_NOTICE": "handle_insufficient_notice",
        "STUDENT_LIMIT_EXCEEDED": "handle_limit_exceeded",
        "RESOURCE_UNAVAILABLE": "handle_unavailable",
        "ENTITY_NOT_FOUND": "handle_not_found",
        "INVALID_STATE_TRANSITION": "handle_invalid_transition",
        "TERMINAL_STATE": "handle_terminal_state"
    }
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def handle_error(self, response: requests.Response) -> Dict[str, Any]:
        """Processa erro estruturado e retorna ação recomendada"""
        try:
            error_data = response.json()
            error_code = error_data.get("error")
            
            self.logger.warning(
                f"API Error [{response.status_code}] {error_code}: {error_data.get('message')}"
            )
            
            handler_name = self.HANDLERS.get(error_code, "handle_generic")
            handler = getattr(self, handler_name, self.handle_generic)
            
            return {
                "success": False,
                "error_code": error_code,
                "message": error_data.get("message"),
                "details": error_data.get("details", {}),
                "action": handler(error_data)
            }
        
        except Exception as e:
            self.logger.error(f"Erro ao processar resposta de erro: {e}")
            return {
                "success": False,
                "error_code": "UNKNOWN",
                "message": "Erro desconhecido",
                "action": "retry"
            }
    
    def handle_conflict(self, error_data):
        return {
            "type": "conflict",
            "message": "Escolha outro período",
            "details": error_data["details"]["conflicting_period"]
        }
    
    def handle_suspended(self, error_data):
        return {
            "type": "blocked_user",
            "message": "Contate suporte",
            "reason": error_data["details"]["reason"]
        }
    
    def handle_insufficient_notice(self, error_data):
        return {
            "type": "timing",
            "message": "Tente cancelar mais cedo",
            "details": error_data["details"]
        }
    
    def handle_generic(self, error_data):
        return {
            "type": "generic",
            "message": "Operação não permitida",
            "details": error_data.get("details")
        }
```

---

## 10. Exemplo Completo: Cliente em Python

```python
import requests
import json
from datetime import datetime, timedelta

class ReservaClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
    
    def criar_reserva(self, usuario_id: str, recurso_id: str, 
                     data_inicio: str, data_fim: str):
        """Cria reserva com tratamento de erro estruturado"""
        payload = {
            "usuario_id": usuario_id,
            "recurso_id": recurso_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        
        response = self.session.post(f"{self.base_url}/reservas/", json=payload)
        
        # Sucesso
        if response.status_code == 201:
            return response.json()
        
        # Erro estruturado
        error = response.json()
        error_code = error.get("error")
        
        if error_code == "RESERVATION_CONFLICT":
            conflicting = error["details"]["conflicting_period"]
            raise ReservationError(
                f"Período ocupado de {conflicting['start']} a {conflicting['end']}"
            )
        
        elif error_code == "USER_SUSPENDED":
            raise AuthError(f"Usuário bloqueado: {error['details']['reason']}")
        
        elif error_code == "STUDENT_LIMIT_EXCEEDED":
            raise LimitError(
                f"Limite atingido: {error['details']['current_active_reservations']}/"
                f"{error['details']['limit']}"
            )
        
        elif error_code == "INSUFFICIENT_NOTICE":
            raise TimingError(
                f"Cancelamento requer {error['details']['minimum_hours']} hora(s) de antecedência"
            )
        
        elif error_code == "RESOURCE_UNAVAILABLE":
            raise ResourceError(
                f"Recurso indisponível ({error['details']['status']})"
            )
        
        elif error_code == "ENTITY_NOT_FOUND":
            raise NotFoundError(
                f"{error['details']['entity_type']} não encontrado"
            )
        
        else:
            raise APIError(f"Erro desconhecido: {error_code}")

# Uso
client = ReservaClient("http://localhost:8000")

try:
    reserva = client.criar_reserva(
        usuario_id="user-123",
        recurso_id="resource-456",
        data_inicio="2024-03-15T14:00:00",
        data_fim="2024-03-15T16:00:00"
    )
    print(f"✅ Reserva criada: {reserva['id']}")

except ReservationError as e:
    print(f"❌ Conflito: {e}")

except UserLimitError as e:
    print(f"❌ Limite excedido: {e}")

except Exception as e:
    print(f"❌ Erro: {e}")
```

---

## 🎯 Vantagens da Estrutura Padronizada

1. **Programável**: Clientes podem reagem diferente para cada erro
2. **i18n**: Frontend traduz código `RESERVATION_CONFLICT` → Português/Inglês
3. **Auditoria**: Logs contêm `error_code`, `details` para investigação
4. **Debugging**: `details` fornece contexto exato do problema
5. **UX**: Mensagens legíveis + contexto = melhor experiência

---

