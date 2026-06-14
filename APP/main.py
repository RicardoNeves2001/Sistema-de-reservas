import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from sqlalchemy.exc import OperationalError

from APP.core.database import Base, engine
from APP.routers import reserva_router
from APP.exceptions import BusinessRuleException, ErrorResponse

app = FastAPI(title="Sistema Multiúso de Reservas", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    retries = 5
    while retries > 0:
        try:
            Base.metadata.create_all(bind=engine)
            break
        except OperationalError:
            retries -= 1
            if retries == 0:
                raise
            time.sleep(2)

# Exception Handler para exceções de negócio estruturadas
@app.exception_handler(BusinessRuleException)
async def business_rule_exception_handler(request: Request, exc: BusinessRuleException):
    """Retorna erro estruturado com código, mensagem e detalhes"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )

# Exception Handler para HTTPException (EntityNotFoundException, etc)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Retorna erro estruturado para HTTPException padrão"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )

# Exception Handler Global para erros inesperados
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Captura erros inesperados e retorna erro genérico"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Ocorreu um erro inesperado no servidor.",
            "details": {}
        }
    )

app.include_router(reserva_router.router)