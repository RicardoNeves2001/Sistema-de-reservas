import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from APP.core.database import Base

class UsuarioStatus(PyEnum):
    ATIVO = "ATIVO"
    SUSPENSO = "SUSPENSO"

class TipoUsuario(PyEnum):
    ALUNO = "ALUNO"
    PROFESSOR = "PROFESSOR"
    ADMIN = "ADMIN"

class TipoRecurso(PyEnum):
    LIVRO = "LIVRO"
    ESPACO = "ESPACO"
    EQUIPAMENTO = "EQUIPAMENTO"

class RecursoStatus(PyEnum):
    DISPONIVEL = "DISPONIVEL"
    MANUTENCAO = "MANUTENCAO"
    INATIVO = "INATIVO"

class ReservaStatus(PyEnum):
    SOLICITADA = "SOLICITADA"
    CONFIRMADA = "CONFIRMADA"
    EM_USO = "EM_USO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"
    REJEITADA = "REJEITADA"

class Usuario(Base):
    __tablename__ = "usuario"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    tipo_usuario = Column(Enum(TipoUsuario), nullable=False)
    status = Column(Enum(UsuarioStatus), default=UsuarioStatus.ATIVO, nullable=False)

class Recurso(Base):
    __tablename__ = "recurso"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    tipo_recurso = Column(Enum(TipoRecurso), nullable=False)
    status = Column(Enum(RecursoStatus), default=RecursoStatus.DISPONIVEL, nullable=False)
    localizacao = Column(String(100), nullable=True)

class Reserva(Base):
    __tablename__ = "reserva"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    recurso_id = Column(UUID(as_uuid=True), ForeignKey("recurso.id"), nullable=False)
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=False)
    status = Column(Enum(ReservaStatus), default=ReservaStatus.SOLICITADA, nullable=False)

    # Índice Composto exigido na Migration 2 para a Regra de Negócio RN-001
    __table_args__ = (
        Index('idx_recurso_horario', 'recurso_id', 'data_inicio', 'data_fim'),
    )

class HistoricoStatusReserva(Base):
    __tablename__ = "historico_status_reserva"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reserva_id = Column(UUID(as_uuid=True), ForeignKey("reserva.id"), nullable=False)
    status_anterior = Column(Enum(ReservaStatus), nullable=False)
    status_novo = Column(Enum(ReservaStatus), nullable=False)
    alterado_em = Column(DateTime, default=datetime.utcnow, nullable=False)