"""estrutura inicial

Revision ID: 54427ed611bd
Revises: 
Create Date: 2026-06-14 16:21:18.645927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '54427ed611bd'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usuario',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            'tipo_usuario',
            sa.Enum('ALUNO', 'PROFESSOR', 'ADMIN', name='tipo_usuario'),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum('ATIVO', 'SUSPENSO', name='usuario_status'),
            nullable=False,
        ),
    )

    op.create_table(
        'recurso',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column(
            'tipo_recurso',
            sa.Enum('LIVRO', 'ESPACO', 'EQUIPAMENTO', name='tipo_recurso'),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.Enum('DISPONIVEL', 'MANUTENCAO', 'INATIVO', name='recurso_status'),
            nullable=False,
        ),
        sa.Column('localizacao', sa.String(length=100), nullable=True),
    )

    op.create_table(
        'reserva',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('usuario_id', sa.UUID(), sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('recurso_id', sa.UUID(), sa.ForeignKey('recurso.id'), nullable=False),
        sa.Column('data_inicio', sa.DateTime(), nullable=False),
        sa.Column('data_fim', sa.DateTime(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'SOLICITADA',
                'CONFIRMADA',
                'EM_USO',
                'CONCLUIDA',
                'CANCELADA',
                'REJEITADA',
                name='reserva_status',
            ),
            nullable=False,
        ),
    )

    op.create_index(
        'idx_recurso_horario',
        'reserva',
        ['recurso_id', 'data_inicio', 'data_fim'],
    )

    op.create_table(
        'historico_status_reserva',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('reserva_id', sa.UUID(), sa.ForeignKey('reserva.id'), nullable=False),
        sa.Column(
            'status_anterior',
            sa.Enum('SOLICITADA', 'CONFIRMADA', 'EM_USO', 'CONCLUIDA', 'CANCELADA', 'REJEITADA', name='reserva_status'),
            nullable=False,
        ),
        sa.Column(
            'status_novo',
            sa.Enum('SOLICITADA', 'CONFIRMADA', 'EM_USO', 'CONCLUIDA', 'CANCELADA', 'REJEITADA', name='reserva_status'),
            nullable=False,
        ),
        sa.Column('alterado_em', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('historico_status_reserva')
    op.drop_index('idx_recurso_horario', table_name='reserva')
    op.drop_table('reserva')
    op.drop_table('recurso')
    op.drop_table('usuario')
