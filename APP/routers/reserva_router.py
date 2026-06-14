from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID
from APP.core.database import get_db
from APP.schemas.schemas import ReservaCreate, ReservaResponse, ReservaPaginated, UpdateStatusRequest
from APP.services.reserva_service import ReservaService
from APP.repositories.reserva_repository import ReservaRepository

router = APIRouter(prefix="/reservas", tags=["Reservas"])

@router.post("/", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
def criar_reserva(payload: ReservaCreate, db: Session = Depends(get_db)):
    # Roteador delega 100% da regra de negócio para a camada de Service
    return ReservaService.criar_reserva(db, payload)

@router.get("/", response_model=ReservaPaginated)
def listar_reservas_paginadas(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    total, resultados = ReservaRepository.listar_paginado(db, limit, offset)
    return {"total": total, "limit": limit, "offset": offset, "results": resultados}

@router.patch("/{id}/status", response_model=ReservaResponse)
def alterar_status_reserva(id: UUID, payload: UpdateStatusRequest, db: Session = Depends(get_db)):
    return ReservaService.atualizar_status(db, id, payload.novo_status)