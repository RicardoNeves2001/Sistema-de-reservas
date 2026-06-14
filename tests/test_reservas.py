from datetime import datetime, timedelta
import uuid
from APP.models.models import (
    Usuario,
    TipoUsuario,
    UsuarioStatus,
    Recurso,
    TipoRecurso,
    RecursoStatus,
    Reserva,
    ReservaStatus,
)


def test_criar_reserva_sucesso(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Lucas", email="lucas@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Auditório Central", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "SOLICITADA"


def test_criar_reserva_usuario_suspenso(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Carol Suspensa", email="carol@univ.edu", tipo_usuario=TipoUsuario.ALUNO, status=UsuarioStatus.SUSPENSO))
    db.add(Recurso(id=r_id, nome="Sala de Estudo", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 403
    assert response.json()["error"] == "USER_SUSPENDED"


def test_criar_reserva_recurso_manutencao(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Diego", email="diego@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Projetor Defeituoso", tipo_recurso=TipoRecurso.EQUIPAMENTO, status=RecursoStatus.MANUTENCAO))
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 400
    assert response.json()["error"] == "RESOURCE_UNAVAILABLE"


def test_criar_reserva_sobreposicao(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Ester", email="ester@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Sala de Aula 1", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    reserva_existente = Reserva(
        usuario_id=u_id,
        recurso_id=r_id,
        data_inicio=datetime.utcnow() + timedelta(days=1),
        data_fim=datetime.utcnow() + timedelta(days=1, hours=2),
        status=ReservaStatus.SOLICITADA,
    )
    db.add(reserva_existente)
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1, hours=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=3)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 409
    assert response.json()["error"] == "RESERVATION_CONFLICT"


def test_criar_reserva_limite_aluno(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Felipe", email="felipe@univ.edu", tipo_usuario=TipoUsuario.ALUNO, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Laboratório 2", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    for i in range(3):
        reserva = Reserva(
            usuario_id=u_id,
            recurso_id=r_id,
            data_inicio=datetime.utcnow() + timedelta(days=i + 1),
            data_fim=datetime.utcnow() + timedelta(days=i + 1, hours=2),
            status=ReservaStatus.SOLICITADA,
        )
        db.add(reserva)
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=5, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "STUDENT_LIMIT_EXCEEDED"


def test_cancelar_reserva_com_menor_1_hora(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Gabriela", email="gabriela@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Sala VIP", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    reserva = Reserva(
        usuario_id=u_id,
        recurso_id=r_id,
        data_inicio=datetime.utcnow() + timedelta(minutes=30),
        data_fim=datetime.utcnow() + timedelta(hours=2),
        status=ReservaStatus.CONFIRMADA,
    )
    db.add(reserva)
    db.commit()

    payload = {"novo_status": "CANCELADA"}
    response = client.patch(f"/reservas/{reserva.id}/status", json=payload)

    assert response.status_code == 422
    assert response.json()["error"] == "INSUFFICIENT_NOTICE"


def test_cancelar_reserva_com_sucesso(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Helena", email="helena@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Auditório 2", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    reserva = Reserva(
        usuario_id=u_id,
        recurso_id=r_id,
        data_inicio=datetime.utcnow() + timedelta(hours=2),
        data_fim=datetime.utcnow() + timedelta(hours=4),
        status=ReservaStatus.CONFIRMADA,
    )
    db.add(reserva)
    db.commit()

    payload = {"novo_status": "CANCELADA"}
    response = client.patch(f"/reservas/{reserva.id}/status", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELADA"


def test_criar_reserva_recurso_inativo(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Ivan", email="ivan@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Recurso Descontinuado", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.INATIVO))
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 400
    assert response.json()["error"] == "RESOURCE_UNAVAILABLE"


def test_professor_multiplas_reservas_sem_limite(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Joana", email="joana@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Sala Multi", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    for i in range(5):
        reserva = Reserva(
            usuario_id=u_id,
            recurso_id=r_id,
            data_inicio=datetime.utcnow() + timedelta(days=i + 1),
            data_fim=datetime.utcnow() + timedelta(days=i + 1, hours=2),
            status=ReservaStatus.SOLICITADA,
        )
        db.add(reserva)
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=10, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 201


def test_usuario_ou_recurso_nao_encontrado(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 404
    assert response.json()["error"] == "ENTITY_NOT_FOUND"


def test_listar_reservas_paginadas(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Kevin", email="kevin@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Sala Listagem", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    for i in range(3):
        reserva = Reserva(
            usuario_id=u_id,
            recurso_id=r_id,
            data_inicio=datetime.utcnow() + timedelta(days=i + 1),
            data_fim=datetime.utcnow() + timedelta(days=i + 1, hours=2),
            status=ReservaStatus.SOLICITADA,
        )
        db.add(reserva)
    db.commit()

    response = client.get("/reservas/?limit=10&offset=0")

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert len(response.json()["results"]) == 3


def test_cancelar_reserva_nao_confirmada(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Lucia", email="lucia@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Sala Cancelamento", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    reserva = Reserva(
        usuario_id=u_id,
        recurso_id=r_id,
        data_inicio=datetime.utcnow() + timedelta(hours=2),
        data_fim=datetime.utcnow() + timedelta(hours=4),
        status=ReservaStatus.SOLICITADA,
    )
    db.add(reserva)
    db.commit()

    payload = {"novo_status": "CANCELADA"}
    response = client.patch(f"/reservas/{reserva.id}/status", json=payload)

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_STATE_TRANSITION"


def test_sobreposicao_reserva_cancelada_nao_impede(client, db):
    u_id = uuid.uuid4()
    r_id = uuid.uuid4()
    db.add(Usuario(id=u_id, nome="Marco", email="marco@univ.edu", tipo_usuario=TipoUsuario.PROFESSOR, status=UsuarioStatus.ATIVO))
    db.add(Recurso(id=r_id, nome="Sala Overlap", tipo_recurso=TipoRecurso.ESPACO, status=RecursoStatus.DISPONIVEL))
    db.commit()

    reserva_cancelada = Reserva(
        usuario_id=u_id,
        recurso_id=r_id,
        data_inicio=datetime.utcnow() + timedelta(days=1),
        data_fim=datetime.utcnow() + timedelta(days=1, hours=2),
        status=ReservaStatus.CANCELADA,
    )
    db.add(reserva_cancelada)
    db.commit()

    payload = {
        "usuario_id": str(u_id),
        "recurso_id": str(r_id),
        "data_inicio": (datetime.utcnow() + timedelta(days=1, hours=1)).isoformat(),
        "data_fim": (datetime.utcnow() + timedelta(days=1, hours=3)).isoformat(),
    }

    response = client.post("/reservas/", json=payload)

    assert response.status_code == 201
