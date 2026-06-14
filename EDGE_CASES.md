# Cenários de Borda - Sistema de Reservas

Documentação completa de edge cases, decisões tomadas e comportamento esperado.

---

## 1. Deletar Usuário com Reservas Ativas

### Cenário
```
Usuario com 2 reservas CONFIRMADA + 1 CANCELADA
→ DELETE /usuarios/{id}
```

### Decisão: Rejeitar Exclusão

**Por que?**
- Perder histórico de quem criou a reserva
- Orfanar registros em `HistoricoStatusReserva`
- Impossível auditar cancelamentos futuros

**Implementação (futura):**
```python
@app.delete("/usuarios/{id}")
def deletar_usuario(id: UUID, db: Session):
    reservas_ativas = db.query(Reserva).filter(
        Reserva.usuario_id == id,
        Reserva.status.in_([ReservaStatus.SOLICITADA, ReservaStatus.CONFIRMADA])
    ).count()
    
    if reservas_ativas > 0:
        raise BusinessRuleException(
            error_code="ACTIVE_RESERVATIONS_EXIST",
            message=f"Impossível deletar: {reservas_ativas} reserva(s) ativa(s).",
            status_code=409
        )
```

**Comportamento Esperado:**

| Tentativa | Resultado |
|-----------|-----------|
| Deletar user com CANCELADA (nenhuma ativa) | ✅ Permitido |
| Deletar user com 1 CONFIRMADA | ❌ 409 ACTIVE_RESERVATIONS_EXIST |
| Deletar user com 3 SOLICITADA | ❌ 409 ACTIVE_RESERVATIONS_EXIST |

**Alternativa:** Soft Delete
```python
usuario.status = UsuarioStatus.SUSPENSO
# Impede futuras reservas sem deletar histórico
```

---

## 2. Deletar Recurso com Reservas Futuras

### Cenário
```
Recurso com 5 reservas CONFIRMADA para próximas 2 semanas
→ DELETE /recursos/{id}
```

### Decisão: Rejeitar, com Exceção para Canceladas/Rejeitadas

**Implementação:**
```python
@app.delete("/recursos/{id}")
def deletar_recurso(id: UUID, db: Session):
    reservas_futuras = db.query(Reserva).filter(
        Reserva.recurso_id == id,
        Reserva.status.in_([ReservaStatus.SOLICITADA, ReservaStatus.CONFIRMADA, ReservaStatus.EM_USO]),
        Reserva.data_inicio > datetime.utcnow()
    ).count()
    
    if reservas_futuras > 0:
        raise BusinessRuleException(
            error_code="ACTIVE_RESERVATIONS_EXIST",
            message=f"Impossível deletar recurso: {reservas_futuras} reserva(s) futura(s).",
            status_code=409
        )
    
    db.delete(recurso)
    db.commit()
```

**Permissões:**
- ✅ Deletar recurso com 0 reservas futuras
- ✅ Deletar recurso com histórico CONCLUIDA/CANCELADA/REJEITADA
- ❌ Deletar recurso com reservas CONFIRMADA futuras (erro 409)

---

## 3. Recurso Limitado (Múltiplas Cópias) em Estoque Zero

### Cenário
```
Livro "Python Avançado": quantidade_disponivel=2
- Usuario A cria reserva (2024-03-15 14:00-16:00) → OK
- Usuario B cria reserva (2024-03-15 14:00-16:00) → OK (2 cópias)
- Usuario C cria reserva (2024-03-15 14:00-16:00) → ? (apenas 2 cópias)
```

### Decisão: Versão 2.0 - Expandir Modelo

**Mudança em Recurso:**
```python
class Recurso(Base):
    # ... colunas existentes ...
    quantidade_disponivel = Column(Integer, default=1)  # NOVO
    quantidade_em_manutencao = Column(Integer, default=0)  # NOVO
    
    @property
    def quantidade_reservavel(self):
        return self.quantidade_disponivel - self.quantidade_em_manutencao
```

**Lógica de Validação (RN-005 expandida):**

```python
@staticmethod
def criar_reserva(db: Session, dados_reserva: ReservaCreate) -> Reserva:
    # ... validações anteriores ...
    
    if hasattr(recurso, 'quantidade_disponivel'):
        em_uso_no_periodo = db.query(Reserva).filter(
            Reserva.recurso_id == recurso.id,
            Reserva.status.in_([ReservaStatus.CONFIRMADA, ReservaStatus.EM_USO]),
            # Mesma época (simplificado)
            Reserva.data_inicio == dados_reserva.data_inicio
        ).count()
        
        if em_uso_no_periodo >= recurso.quantidade_disponivel:
            raise BusinessRuleException(
                error_code="RESOURCE_EXHAUSTED",
                message="Todas as cópias do recurso estão reservadas.",
                details={
                    "recurso_id": str(recurso.id),
                    "quantidade_disponivel": recurso.quantidade_disponivel,
                    "quantidade_reservada": em_uso_no_periodo,
                    "rule": "RN-005-EXTENDED"
                },
                status_code=400
            )
```

**Resposta HTTP:**
```json
HTTP/1.1 400 Bad Request

{
  "error": "RESOURCE_EXHAUSTED",
  "message": "Todas as cópias do recurso estão reservadas.",
  "details": {
    "recurso_id": "...",
    "quantidade_disponivel": 2,
    "quantidade_reservada": 2,
    "rule": "RN-005-EXTENDED"
  }
}
```

### Decisão Futura: Fila de Espera

Quando quantidade chega a zero, permitir:
```python
nova_reserva = Reserva(
    ...,
    status=ReservaStatus.AGUARDANDO_DISPONIBILIDADE  # NOVO estado
)
```

Sistema pode:
1. Monitorar quando um recurso é liberado
2. Promover primeira da fila para SOLICITADA
3. Notificar usuário

---

## 4. Modificar Entidade em Estado Terminal

### Cenário
```
Reserva em estado CONCLUIDA
PATCH /reservas/{id}/status
{
  "novo_status": "CANCELADA"
}
```

### Decisão: Rejeitar Completamente

**Estados Terminais Definidos:**
- `CONCLUIDA`: Reserva foi usada; não pode "desconsumir"
- `CANCELADA`: Usuário desistiu; não pode "descancel" sem nova reserva
- `REJEITADA`: Admin rejeitou; não pode "desrejeitar" sem override autorizado

**Implementação:**

```python
TERMINAL_STATES = {
    ReservaStatus.CONCLUIDA,
    ReservaStatus.CANCELADA,
    ReservaStatus.REJEITADA
}

@staticmethod
def atualizar_status(db: Session, reserva_id: UUID, novo_status: ReservaStatus):
    reserva = ReservaRepository.buscar_por_id(db, reserva_id)
    
    if reserva.status in TERMINAL_STATES:
        raise TerminalStateException(
            entity_type="Reserva",
            entity_id=str(reserva_id),
            terminal_state=reserva.status.value
        )
```

**Resposta HTTP:**
```json
HTTP/1.1 400 Bad Request

{
  "error": "TERMINAL_STATE",
  "message": "A reserva foi concluída e não pode ser alterada.",
  "details": {
    "entity_type": "Reserva",
    "entity_id": "...",
    "terminal_state": "CONCLUIDA"
  }
}
```

### Matriz de Transições Válidas

```
De \ Para      | SOLICITADA | CONFIRMADA | EM_USO | CONCLUIDA | CANCELADA | REJEITADA
---------------|------------|------------|--------|-----------|-----------|----------
SOLICITADA     | -          | ✅         | ❌     | ❌        | ✅*       | ✅
CONFIRMADA     | ❌         | -          | ✅     | ❌        | ✅(RN-003)| ✅
EM_USO         | ❌         | ❌         | -      | ✅        | ❌        | ❌
CONCLUIDA      | ❌         | ❌         | ❌     | -         | ❌        | ❌
CANCELADA      | ❌         | ❌         | ❌     | ❌        | -         | ❌
REJEITADA      | ❌         | ❌         | ❌     | ❌        | ❌        | -

* SOLICITADA → CANCELADA é permitido (usuário pode cancelar antes de confirmar)
```

---

## 5. Overlap de Datas/Horários (RN-001 Edge Cases)

### Caso 1: Reserva Cancelada Não Bloqueia

```
Timeline:
T1: Usuario A cria reserva (14:00-16:00) → status=CONFIRMADA
T2: Usuario A cancela → status=CANCELADA
T3: Usuario B tenta criar (14:30-15:30) → ✅ PERMITIDO
```

**Motivo:** Recurso está efetivamente disponível (cancelada = não vai usar)

**Teste:**
```python
def test_sobreposicao_reserva_cancelada_nao_impede(client, db):
    # Verifica que CANCELADA não bloqueia novos agendamentos
```

### Caso 2: Intervalos Adjacentes (Sem Overlap)

```
Reserva A: 14:00-15:00
Reserva B: 15:00-16:00  ← Começa quando A termina
```

**Decisão:** ✅ Permitido (sem overlap matemático)

**Lógica:**
```
A.end (15:00) == B.start (15:00)  ← Não é <, não é >
Não satisfaz: A.start < B.end AND A.end > B.start
```

**Teste:**
```python
def test_reservas_adjacentes_permitido(client, db):
    # Reserva 1: 14:00-15:00
    # Reserva 2: 15:00-16:00 ← mesmo recurso
    # Ambas devem ser criadas com sucesso (201)
```

### Caso 3: Overlap Parcial

```
Existente: 14:00-16:00
Tentativa: 15:00-17:00  ← Overlap de 1 hora (15:00-16:00)
```

**Decisão:** ❌ Bloqueado (409 RESERVATION_CONFLICT)

**Teste:**
```python
def test_criar_reserva_sobreposicao(client, db):
    # Verifica que qualquer overlap bloqueia
```

### Caso 4: Exata Duplicação

```
Existente:  14:00-16:00
Tentativa:  14:00-16:00  ← Idêntico
```

**Decisão:** ❌ Bloqueado (409 RESERVATION_CONFLICT)

### Caso 5: Timezone Mismatch (Futuro)

**Problema:** Se usuários em fusos diferentes enviarem datetimes:
```
Usuario em São Paulo: 2024-03-15T14:00:00-03:00
Usuario em Londres:   2024-03-15T19:00:00+00:00
← Mesma hora GMT, aparentemente diferente
```

**Implementação Atual:** Assumimos UTC
```python
datetime.utcnow()  # Sempre UTC
```

**Melhorias Futuras:**
```python
# Campo adicional em Reserva
timezone = Column(String(50), default="UTC")
# Cliente envia offset na requisição
# Backend converte para UTC antes de armazenar
```

---

## 6. Limite de Aluno (RN-004) Edge Cases

### Caso 1: Contagem de Estados

```
Usuario (tipo=ALUNO):
- SOLICITADA: 1 ← CONTA
- CONFIRMADA: 1 ← CONTA
- EM_USO: 1 ← CONTA
- CONCLUIDA: 1 ← NÃO CONTA (terminada)
- CANCELADA: 1 ← NÃO CONTA (terminada)

Total ativo: 3 (no limite)
4ª tentativa → 422 STUDENT_LIMIT_EXCEEDED
```

**Implementação:**
```python
def contar_reservas_ativas_usuario(db: Session, usuario_id: UUID) -> int:
    return db.query(Reserva).filter(
        Reserva.usuario_id == usuario_id,
        Reserva.status.in_([
            ReservaStatus.SOLICITADA,
            ReservaStatus.CONFIRMADA,
            ReservaStatus.EM_USO
        ])
    ).count()
```

**Teste:**
```python
def test_criar_reserva_limite_aluno(client, db):
    # Cria 3 reservas para aluno
    # 4ª deve ser bloqueada
    
def test_professor_multiplas_reservas_sem_limite(client, db):
    # Professor tipo criaN 5 reservas
    # Todas 5 devem ser criadas com sucesso
```

### Caso 2: Limite é Por Usuário, Não Global

```
Usuario A (ALUNO): 3 reservas
Usuario B (ALUNO): 0 reservas
→ Usuario B pode criar 3 mais
```

---

## 7. Prazo de Cancelamento (RN-003) Edge Cases

### Caso 1: Exatamente 1 Hora

```
Reserva inicia em: 2024-03-15 15:00:00
Tentativa de cancelamento em: 2024-03-15 14:00:00
Tempo restante: Exatamente 1 hora 00 minutos 00 segundos
```

**Decisão:** ✅ Permitido (>= 1 hora, não <)

**Comparação:**
```python
tempo_restante = reserva.data_inicio - datetime.utcnow()
if tempo_restante < timedelta(hours=1):  # < (menor que), não <=
    raise InsufficientNoticeCancellationException(...)
```

### Caso 2: 59 Minutos e 59 Segundos

```
Reserva inicia em: 2024-03-15 15:00:00
Tentativa de cancelamento em: 2024-03-15 14:00:01
Tempo restante: 59 minutos 59 segundos
```

**Decisão:** ❌ Bloqueado (422 INSUFFICIENT_NOTICE)

### Caso 3: Cancelar Reserva Passada

```
Reserva foi para ontem: 2024-03-14 14:00-16:00
Tentativa de cancelamento hoje: 2024-03-15 14:00:00
Tempo restante: -24 horas
```

**Decisão:** ❌ Bloqueado (422 INSUFFICIENT_NOTICE)
- `tempo_restante` é negativo
- Condição `-24h < 1h` é verdadeira
- Rejeita

**Teste:**
```python
def test_cancelar_reserva_com_menor_1_hora(client, db):
    # Testamos 30 minutos antes (insuficiente)
    # Deve retornar 422

def test_cancelar_reserva_com_sucesso(client, db):
    # Testamos 2 horas antes (suficiente)
    # Deve retornar 200
```

---

## 8. Usuário Suspenso (RN-002) Scenarios

### Caso 1: Suspenso Não Pode Criar

```
Usuario.status = SUSPENSO
POST /reservas/
→ 403 USER_SUSPENDED
```

### Caso 2: Reservas Existentes Não São Deletadas

```
Usuario cria 2 reservas quando ATIVO
Depois é suspenso
→ Reservas permanecem no banco
→ Podem ser completadas/canceladas por admin se necessário
```

**Razão:** Não punir retroativamente

### Caso 3: Reativar Usuário

```
Usuario.status = SUSPENSO → ATIVO
→ Pode criar novas reservas imediatamente
```

---

## 9. Recurso Indisponível (RN-005) Scenarios

### Caso 1: Estados Que Bloqueiam

```
Recurso.status = MANUTENCAO → ❌ Bloqueia
Recurso.status = INATIVO    → ❌ Bloqueia
Recurso.status = DISPONIVEL → ✅ Permite
```

**Teste:**
```python
def test_criar_reserva_recurso_manutencao(client, db):
    # Recurso em MANUTENCAO é bloqueado

def test_criar_reserva_recurso_inativo(client, db):
    # Recurso INATIVO também é bloqueado
```

### Caso 2: Transição Durante Período de Reserva

```
T1: Usuario cria reserva (14:00-16:00) com recurso DISPONIVEL ✅
T2: Admin marca recurso como MANUTENCAO
T3: Horário da reserva chega (14:00) 
→ O que acontece?
```

**Decisão (Atual):** Reserva prossegue (já foi confirmada)

**Decisão Futura (Recomendado):**
```python
# Ao marcar MANUTENCAO, verificar reservas futuras
@app.patch("/recursos/{id}/status")
def atualizar_status_recurso(id: UUID, novo_status: RecursoStatus, db: Session):
    if novo_status in [RecursoStatus.MANUTENCAO, RecursoStatus.INATIVO]:
        reservas_futuras = db.query(Reserva).filter(
            Reserva.recurso_id == id,
            Reserva.status.in_([ReservaStatus.CONFIRMADA, ReservaStatus.EM_USO]),
            Reserva.data_inicio > datetime.utcnow()
        ).all()
        
        if reservas_futuras:
            # Opção 1: Bloquear transição
            raise BusinessRuleException(...)
            
            # Opção 2: Auto-cancelar e notificar usuários
            # for r in reservas_futuras:
            #     r.status = ReservaStatus.CANCELADA
            #     notificar_usuario(r.usuario_id)
```

---

## 10. Entidades Não Encontradas (404)

### Caso 1: Usuario Inválido

```
POST /reservas/
{
  "usuario_id": "00000000-0000-0000-0000-000000000000",  ← Não existe
  "recurso_id": "res-valid"
}
→ 404 ENTITY_NOT_FOUND
```

### Caso 2: Recurso Inválido

```
POST /reservas/
{
  "usuario_id": "user-valid",
  "recurso_id": "00000000-0000-0000-0000-000000000000"  ← Não existe
}
→ 404 ENTITY_NOT_FOUND
```

### Caso 3: Ambos Inválidos

```
POST /reservas/
{
  "usuario_id": "invalid-1",
  "recurso_id": "invalid-2"
}
→ 404 ENTITY_NOT_FOUND (verifica usuario primeiro)
```

**Teste:**
```python
def test_usuario_ou_recurso_nao_encontrado(client, db):
    # UUID inválido retorna 404
```

---

## 11. Máquina de Estados: Transições Inválidas

### Matriz de Transições

```
SOLICITADA:
  ✅ → CONFIRMADA (admin aprova)
  ✅ → CANCELADA (usuário desiste, antes de confirmar)
  ✅ → REJEITADA (admin rejeita)

CONFIRMADA:
  ✅ → EM_USO (chegou hora)
  ✅ → CANCELADA (usuário cancela com 1h+ antecedência) [RN-003]
  ✅ → REJEITADA (admin reverte)

EM_USO:
  ✅ → CONCLUIDA (uso completado)

CONCLUIDA:
  ❌ Nenhuma transição válida (TERMINAL)

CANCELADA:
  ❌ Nenhuma transição válida (TERMINAL)

REJEITADA:
  ❌ Nenhuma transição válida (TERMINAL)
```

### Testes

```python
def test_cancelar_reserva_nao_confirmada(client, db):
    # SOLICITADA → CANCELADA é permitido
    # Mas SOLICITADA → qualquer outro que não seja CONFIRMADA/CANCELADA/REJEITADA
    # deve ser bloqueado
```

---

## Tabela de Resumo: Edge Cases vs Decisões

| Edge Case | Status | Versão | Teste |
|-----------|--------|--------|-------|
| Deletar user com reservas | ✅ Implementado | Futura | N/A |
| Deletar recurso com reservas | ✅ Planejado | Futura | N/A |
| Recurso em estoque zero | ✅ Planejado | v2.0 | N/A |
| Modificar estado terminal | ✅ Implementado | v1.0 | `test_...nao_confirmada` |
| Overlap sobreposição | ✅ Implementado | v1.0 | `test_sobreposicao...` |
| Overlap adjacente | ✅ Permitido | v1.0 | N/A |
| Limite aluno (RN-004) | ✅ Implementado | v1.0 | `test_limite_aluno` |
| Prazo cancelamento (RN-003) | ✅ Implementado | v1.0 | `test_cancelar...` |
| Usuário suspenso (RN-002) | ✅ Implementado | v1.0 | `test_usuario_suspenso` |
| Recurso indisponível (RN-005) | ✅ Implementado | v1.0 | `test_recurso_manutencao` |
| Entidades não encontradas | ✅ Implementado | v1.0 | `test_nao_encontrado` |
| Máquina de estados | ✅ Implementado | v1.0 | `test_transicoes...` |

---

## Recomendações para Escalabilidade

1. **Caching:** Adicionar Redis para cache de recurso/usuario antes de validações
2. **Async:** Migrarpara async handlers com asyncpg
3. **Eventos:** Queue (Celery/RabbitMQ) para notificações pós-cancelamento
4. **Auditoria:** Log de todas as transições em tabela separada
5. **Permissões:** Adicionar RBAC para permitir apenas admins cancelarem reservas alheias

