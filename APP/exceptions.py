"""
Módulo de Exceções Estruturadas para Negócio

Padroniza todas as respostas de erro com código, mensagem e detalhes contextuais.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status

class ErrorResponse:
    """Modelo de resposta de erro estruturada"""
    def __init__(self, error: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.error = error
        self.message = message
        self.details = details or {}
    
    def to_dict(self):
        return {
            "error": self.error,
            "message": self.message,
            "details": self.details
        }


class BusinessRuleException(HTTPException):
    """Exceção base para violações de regras de negócio
    
    Exemplo:
        raise BusinessRuleException(
            error_code="RESERVATION_CONFLICT",
            message="Já existe uma reserva para este recurso no período.",
            details={"conflicting_period": {"start": "...", "end": "..."}},
            status_code=409
        )
    """
    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 422
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        
        super().__init__(
            status_code=status_code,
            detail=ErrorResponse(
                error=error_code,
                message=message,
                details=self.details
            ).to_dict()
        )


# ============================================================================
# Exceções Específicas de Regra de Negócio (RN-001 até RN-005)
# ============================================================================

class ReservationConflictException(BusinessRuleException):
    """RN-001: Sobreposição de Horários
    
    Levantada quando tenta-se reservar um recurso em período já ocupado.
    """
    def __init__(self, conflicting_period: Dict[str, str], recurso_id: str = None):
        super().__init__(
            error_code="RESERVATION_CONFLICT",
            message="Já existe uma reserva para este recurso no período solicitado.",
            details={
                "conflicting_period": conflicting_period,
                "recurso_id": recurso_id,
                "rule": "RN-001"
            },
            status_code=409
        )


class UserSuspendedException(BusinessRuleException):
    """RN-002: Usuário Suspenso
    
    Levantada quando um usuário com status SUSPENSO tenta criar reserva.
    """
    def __init__(self, usuario_id: str, suspension_reason: str = "Pendências ou suspensões ativas"):
        super().__init__(
            error_code="USER_SUSPENDED",
            message=f"Sua conta possui {suspension_reason.lower()}.",
            details={
                "usuario_id": usuario_id,
                "reason": suspension_reason,
                "rule": "RN-002"
            },
            status_code=403
        )


class InsufficientNoticeCancellationException(BusinessRuleException):
    """RN-003: Prazo Mínimo de Cancelamento
    
    Levantada quando tenta-se cancelar uma reserva com menos de 1 hora de antecedência.
    """
    def __init__(self, reservation_start: str, current_time: str, minimum_hours: int = 1):
        super().__init__(
            error_code="INSUFFICIENT_NOTICE",
            message=f"Reservas só podem ser canceladas com antecedência mínima de {minimum_hours} hora(s).",
            details={
                "reservation_start": reservation_start,
                "current_time": current_time,
                "minimum_hours": minimum_hours,
                "rule": "RN-003"
            },
            status_code=422
        )


class StudentReservationLimitExceededException(BusinessRuleException):
    """RN-004: Limite de Reservas para Aluno
    
    Levantada quando um usuário do tipo ALUNO tenta criar mais de 3 reservas simultâneas.
    """
    def __init__(self, usuario_id: str, current_count: int, limit: int = 3):
        super().__init__(
            error_code="STUDENT_LIMIT_EXCEEDED",
            message=f"Usuários do tipo ALUNO só podem possuir até {limit} reservas ativas simultaneamente.",
            details={
                "usuario_id": usuario_id,
                "current_active_reservations": current_count,
                "limit": limit,
                "exceeding_by": current_count - limit + 1,
                "rule": "RN-004"
            },
            status_code=422
        )


class ResourceUnavailableException(BusinessRuleException):
    """RN-005: Recurso Indisponível
    
    Levantada quando tenta-se reservar um recurso em estado MANUTENCAO ou INATIVO.
    """
    def __init__(self, recurso_id: str, status: str, resource_name: str = None):
        status_description = {
            "MANUTENCAO": "em manutenção",
            "INATIVO": "inativo"
        }.get(status, status.lower())
        
        super().__init__(
            error_code="RESOURCE_UNAVAILABLE",
            message=f"O recurso solicitado encontra-se {status_description} e não pode ser reservado.",
            details={
                "recurso_id": recurso_id,
                "status": status,
                "resource_name": resource_name,
                "rule": "RN-005"
            },
            status_code=400
        )


# ============================================================================
# Exceções de Validação de Dados
# ============================================================================

class EntityNotFoundException(HTTPException):
    """Entidade (Usuário, Recurso, Reserva) não encontrada"""
    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            status_code=404,
            detail={
                "error": "ENTITY_NOT_FOUND",
                "message": f"{entity_type} não encontrado.",
                "details": {
                    "entity_type": entity_type,
                    "entity_id": entity_id
                }
            }
        )


class InvalidStateTransitionException(BusinessRuleException):
    """Tentativa de transição inválida na máquina de estados"""
    def __init__(self, entity_type: str, current_state: str, requested_state: str):
        super().__init__(
            error_code="INVALID_STATE_TRANSITION",
            message=f"Não é permitido transicionar de {current_state} para {requested_state}.",
            details={
                "entity_type": entity_type,
                "current_state": current_state,
                "requested_state": requested_state
            },
            status_code=400
        )


class TerminalStateException(BusinessRuleException):
    """Tentativa de modificar uma entidade em estado terminal"""
    def __init__(self, entity_type: str, entity_id: str, terminal_state: str):
        terminal_states = {
            "CONCLUIDA": "A reserva foi concluída e não pode ser alterada.",
            "CANCELADA": "A reserva foi cancelada e não pode ser alterada.",
            "REJEITADA": "A reserva foi rejeitada e não pode ser alterada."
        }
        message = terminal_states.get(terminal_state, f"A entidade está em estado terminal: {terminal_state}")
        
        super().__init__(
            error_code="TERMINAL_STATE",
            message=message,
            details={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "terminal_state": terminal_state
            },
            status_code=400
        )
