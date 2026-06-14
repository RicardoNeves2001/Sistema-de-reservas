from pydantic import BaseModel, Field, model_validator, EmailStr
from datetime import datetime
from uuid import UUID
from typing import Optional, List
from APP.models.models import TipoUsuario, UsuarioStatus, TipoRecurso, RecursoStatus, ReservaStatus

class ReservaBase(BaseModel):
    usuario_id: UUID
    recurso_id: UUID
    data_inicio: datetime
    data_fim: datetime

class ReservaCreate(ReservaBase):
    # Validador customizado Pydantic v2 para garantir consistência temporal básica
    @model_validator(mode='after')
    def verificar_horarios(self) -> 'ReservaCreate':
        if self.data_fim <= self.data_inicio:
            raise ValueError("A data de término deve ser estritamente posterior à data de início.")
        return self

class ReservaResponse(ReservaBase):
    id: UUID
    status: ReservaStatus

    class Config:
        from_attributes = True

class ReservaPaginated(BaseModel):
    total: int
    limit: int
    offset: int
    results: List[ReservaResponse]

class UpdateStatusRequest(BaseModel):
    novo_status: ReservaStatus