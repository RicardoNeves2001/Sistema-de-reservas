from datetime import datetime, timedelta

from APP.core.database import Base, SessionLocal, engine
from APP.models.models import (
    HistoricoStatusReserva,
    Reserva,
    ReservaStatus,
    Recurso,
    RecursoStatus,
    TipoRecurso,
    TipoUsuario,
    Usuario,
    UsuarioStatus,
)


def create_database() -> None:
    Base.metadata.create_all(bind=engine)


def run_seed() -> None:
    db = SessionLocal()
    try:
        print("Iniciando seed no banco de dados...")

        usuario1 = db.query(Usuario).filter_by(email="aluno1@example.com").first()
        if not usuario1:
            usuario1 = Usuario(
                nome="Alice Aluno",
                email="aluno1@example.com",
                tipo_usuario=TipoUsuario.ALUNO,
                status=UsuarioStatus.ATIVO,
            )
            db.add(usuario1)

        usuario2 = db.query(Usuario).filter_by(email="professor1@example.com").first()
        if not usuario2:
            usuario2 = Usuario(
                nome="Bruno Professor",
                email="professor1@example.com",
                tipo_usuario=TipoUsuario.PROFESSOR,
                status=UsuarioStatus.ATIVO,
            )
            db.add(usuario2)

        recurso1 = db.query(Recurso).filter_by(nome="Sala de Reunião").first()
        if not recurso1:
            recurso1 = Recurso(
                nome="Sala de Reunião",
                tipo_recurso=TipoRecurso.ESPACO,
                status=RecursoStatus.DISPONIVEL,
                localizacao="Bloco A - Térreo",
            )
            db.add(recurso1)

        recurso2 = db.query(Recurso).filter_by(nome="Projetor 4K").first()
        if not recurso2:
            recurso2 = Recurso(
                nome="Projetor 4K",
                tipo_recurso=TipoRecurso.EQUIPAMENTO,
                status=RecursoStatus.DISPONIVEL,
                localizacao="Bloco B - Sala 101",
            )
            db.add(recurso2)

        db.flush()

        reserva1 = (
            db.query(Reserva)
            .filter_by(usuario_id=usuario1.id, recurso_id=recurso1.id)
            .first()
        )
        if not reserva1:
            reserva1 = Reserva(
                usuario_id=usuario1.id,
                recurso_id=recurso1.id,
                data_inicio=datetime.utcnow() + timedelta(hours=1),
                data_fim=datetime.utcnow() + timedelta(hours=2),
                status=ReservaStatus.SOLICITADA,
            )
            db.add(reserva1)
            db.flush()

            historico = HistoricoStatusReserva(
                reserva_id=reserva1.id,
                status_anterior=ReservaStatus.SOLICITADA,
                status_novo=ReservaStatus.CONFIRMADA,
                alterado_em=datetime.utcnow(),
            )
            db.add(historico)

        db.commit()
        print("Seed concluído com sucesso.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_database()
    run_seed()
