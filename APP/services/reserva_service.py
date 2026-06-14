from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from uuid import UUID
from APP.models.models import Reserva, ReservaStatus, Usuario, UsuarioStatus, TipoUsuario, Recurso, RecursoStatus
from APP.schemas.schemas import ReservaCreate
from APP.repositories.reserva_repository import ReservaRepository
from APP.exceptions import (
    EntityNotFoundException,
    UserSuspendedException,
    ResourceUnavailableException,
    StudentReservationLimitExceededException,
    ReservationConflictException,
    InsufficientNoticeCancellationException,
    InvalidStateTransitionException
)

class ReservaService:
    @staticmethod
    def criar_reserva(db: Session, dados_reserva: ReservaCreate) -> Reserva:
        # Busca Entidades para validação de regras de negócio
        usuario = db.query(Usuario).filter(Usuario.id == dados_reserva.usuario_id).first()
        recurso = db.query(Recurso).filter(Recurso.id == dados_reserva.recurso_id).first()

        if not usuario or not recurso:
            raise EntityNotFoundException(
                entity_type="Usuário ou Recurso",
                entity_id=str(dados_reserva.usuario_id) if not usuario else str(dados_reserva.recurso_id)
            )

        # RN-002: Usuários Suspensos Não Reservam
        if usuario.status == UsuarioStatus.SUSPENSO:
            raise UserSuspendedException(
                usuario_id=str(usuario.id),
                suspension_reason="Pendências ou suspensões ativas"
            )

        # RN-005: Recurso em Manutenção ou Inativo Não Pode Ser Reservado
        if recurso.status in [RecursoStatus.MANUTENCAO, RecursoStatus.INATIVO]:
            raise ResourceUnavailableException(
                recurso_id=str(recurso.id),
                status=recurso.status.value,
                resource_name=recurso.nome
            )

        # RN-004: Limite de Reservas Simultâneas por Aluno
        if usuario.tipo_usuario == TipoUsuario.ALUNO:
            total_ativas = ReservaRepository.contar_reservas_ativas_usuario(db, usuario.id)
            if total_ativas >= 3:
                raise StudentReservationLimitExceededException(
                    usuario_id=str(usuario.id),
                    current_count=total_ativas,
                    limit=3
                )

        # RN-001: Bloqueio de Sobreposição de Horário
        conflito = ReservaRepository.verificar_sobreposicao_detalhado(
            db, recurso.id, dados_reserva.data_inicio, dados_reserva.data_fim
        )
        if conflito:
            raise ReservationConflictException(
                conflicting_period={
                    "start": conflito.data_inicio.isoformat(),
                    "end": conflito.data_fim.isoformat()
                },
                recurso_id=str(recurso.id)
            )

        nova_reserva = Reserva(
            usuario_id=dados_reserva.usuario_id,
            recurso_id=dados_reserva.recurso_id,
            data_inicio=dados_reserva.data_inicio,
            data_fim=dados_reserva.data_fim,
            status=ReservaStatus.SOLICITADA
        )
        return ReservaRepository.salvar(db, nova_reserva)

    @staticmethod
    def atualizar_status(db: Session, reserva_id: UUID, novo_status: ReservaStatus) -> Reserva:
        reserva = ReservaRepository.buscar_por_id(db, reserva_id)
        if not reserva:
            raise EntityNotFoundException(
                entity_type="Reserva",
                entity_id=str(reserva_id)
            )

        # Validação de Transição de Estado da Máquina de Estados & RN-003
        if novo_status == ReservaStatus.CANCELADA:
            if reserva.status != ReservaStatus.CONFIRMADA:
                raise InvalidStateTransitionException(
                    entity_type="Reserva",
                    current_state=reserva.status.value,
                    requested_state=novo_status.value
                )
            
            # RN-003: Prazo Limite para Cancelamento (1 Hora de Antecedência)
            tempo_restante = reserva.data_inicio - datetime.utcnow()
            if tempo_restante < timedelta(hours=1):
                raise InsufficientNoticeCancellationException(
                    reservation_start=reserva.data_inicio.isoformat(),
                    current_time=datetime.utcnow().isoformat(),
                    minimum_hours=1
                )

        reserva.status = novo_status
        return ReservaRepository.salvar(db, reserva)