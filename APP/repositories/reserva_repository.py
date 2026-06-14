from datetime import datetime

from sqlalchemy.orm import Session
from uuid import UUID
from APP.models.models import Reserva, ReservaStatus
from APP.schemas.schemas import ReservaCreate

class ReservaRepository:
    @staticmethod
    def buscar_por_id(db: Session, reserva_id: UUID) -> Reserva:
        return db.query(Reserva).filter(Reserva.id == reserva_id).first()

    @staticmethod
    def verificar_sobreposicao(db: Session, recurso_id: UUID, inicio: datetime, fim: datetime) -> bool:
        """Verifica se há sobreposição de horário (retorna booleano)
        
        Lógica matemática da RN-001: Duas reservas se sobrepõem se:
        - A1.start < B.end AND A1.end > B.start
        
        Exclui reservas CANCELADA e REJEITADA (não bloqueiam novos agendamentos)
        """
        conflito = db.query(Reserva).filter(
            Reserva.recurso_id == recurso_id,
            Reserva.status.notin_([ReservaStatus.CANCELADA, ReservaStatus.REJEITADA]),
            Reserva.data_inicio < fim,
            Reserva.data_fim > inicio
        ).first()
        return conflito is not None

    @staticmethod
    def verificar_sobreposicao_detalhado(db: Session, recurso_id: UUID, inicio: datetime, fim: datetime) -> Reserva:
        """Verifica sobreposição e retorna a reserva conflitante (ou None)
        
        Usado para fornecer detalhes contextuais no erro RN-001
        """
        conflito = db.query(Reserva).filter(
            Reserva.recurso_id == recurso_id,
            Reserva.status.notin_([ReservaStatus.CANCELADA, ReservaStatus.REJEITADA]),
            Reserva.data_inicio < fim,
            Reserva.data_fim > inicio
        ).first()
        return conflito

    @staticmethod
    def contar_reservas_ativas_usuario(db: Session, usuario_id: UUID) -> int:
        """Conta reservas ativas de um usuário (RN-004)
        
        Ativas = SOLICITADA, CONFIRMADA ou EM_USO
        """
        return db.query(Reserva).filter(
            Reserva.usuario_id == usuario_id,
            Reserva.status.in_([ReservaStatus.SOLICITADA, ReservaStatus.CONFIRMADA, ReservaStatus.EM_USO])
        ).count()

    @staticmethod
    def listar_paginado(db: Session, limit: int, offset: int):
        """Lista reservas com paginação"""
        total = db.query(Reserva).count()
        results = db.query(Reserva).offset(offset).limit(limit).all()
        return total, results

    @staticmethod
    def salvar(db: Session, reserva: Reserva) -> Reserva:
        """Persiste uma reserva no banco"""
        db.add(reserva)
        db.commit()
        db.refresh(reserva)
        return reserva