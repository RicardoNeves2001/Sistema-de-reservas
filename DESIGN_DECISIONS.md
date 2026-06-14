# Decisões de Design - Sistema Multiúso de Reservas

Documento que justifica as decisões arquiteturais, de modelagem e de implementação do sistema de reservas.

---

## 5.1 Decisões de Design Justificadas

### 1. Relacionamentos de Modelo

#### Decisão: Modelo Simples com Chaves Estrangeiras Diretas

**Estrutura:**
```
Usuario (1) ──→ (N) Reserva ←─ (1) Recurso
```

**Por que não usar outras abordagens?**

| Abordagem | Por que descartada |
|-----------|-------------------|
| **Herança Single Table (STI)** | Usuarios, Recursos com propriedades muito diferentes; STI criaria muitas colunas NULL |
| **Joined Table Inheritance** | Performance: queries complexas com JOINs frequentes; administração mais complexa |
| **Many-to-Many (Recurso ← N:N → Reserva)** | Reserva JÁ É a tabela de junção; redundante adicionar outra |
| **Entidades de Valor (Value Objects)** | Periodo (start/end) faz mais sentido como colunas separadas (permite índices eficientes em range queries) |

**Benefícios da decisão:**
- ✅ Queries de sobreposição (RN-001) são eficientes com índice composto `(recurso_id, data_inicio, data_fim)`
- ✅ Simplicidade: evita JOINs desnecessários em operações CRUD básicas
- ✅ Facilita índices de banco: range queries em `[data_inicio, data_fim)` são triviais
- ✅ Escalabilidade: sem joins complexos, replicação e sharding são viáveis

**Trade-off aceito:**
- Denormalização mínima: `Reserva` armazena `usuario_id` e `recurso_id` em vez de referências estruturadas
- Aceitável porque operações de reserva focam em um usuário + um recurso por vez

---

### 2. Validação: Pydantic vs Camada de Serviço

#### Decisão: Separação Clara de Responsabilidades

**O que vai em Pydantic (`schemas.py`):**

```python
class ReservaCreate(ReservaBase):
    @model_validator(mode='after')
    def verificar_horarios(self) -> 'ReservaCreate':
        if self.data_fim <= self.data_inicio:
            raise ValueError("A data de término deve ser estritamente posterior...")
        return self
```

**Critério**: Validações **estruturais** (tipos, formatos, invariantes sintáticos)
- Data fim > data início (validação matemática pura)
- UUIDs válidos (formato correto)
- Campos obrigatórios vs opcionais

**O que vai em Serviço (`reserva_service.py`):**

```python
# RN-002: Usuário suspenso?
if usuario.status == UsuarioStatus.SUSPENSO:
    raise UserSuspendedException(...)

# RN-001: Sobreposição de horário?
conflito = ReservaRepository.verificar_sobreposicao_detalhado(...)
```

**Critério**: Validações **semânticas** (regras de negócio que dependem de estado do banco)
- Requer consultas ao banco de dados
- Decisões baseadas em múltiplas entidades
- Lógica condicional complexa

**Por que não colocar tudo em Pydantic?**
- ❌ Validators de Pydantic não têm acesso a `Session` do banco
- ❌ Violaria separation of concerns (Pydantic é camada de I/O, não de lógica)
- ❌ Testes unitários de validators seriam difíceis (exigem fixtures DB)

**Por que não colocar tudo em Serviço?**
- ❌ Parsing JSON inválido não seria detectado antes de chegar ao handler
- ❌ Requests com payloads malformados causariam erros genéricos 500 em vez de 422 claros

**Benefício da separação:**
- ✅ Testes de schemas são isolados (sem DB)
- ✅ Testes de serviço focam em regras de negócio
- ✅ Reutilização: schemas validam em múltiplos endpoints

---

### 3. Por que a Migration 2 foi Necessária?

#### Contexto Histórico

**Migration 1 (`54427ed611bd`):**
- Criou estrutura inicial: `Usuario`, `Recurso`, `Reserva`, `HistoricoStatusReserva`
- Criou índice composto `idx_recurso_horario` em `Reserva(recurso_id, data_inicio, data_fim)`

**Migration 2 (`b3c2c4646eed`):**
- ⚠️ **Atualmente vazia** (apenas `pass`)

**Por que criada?**

A migration 2 foi criada como **checkpoint de evolução do esquema**, permitindo:

1. **Possíveis expansões futuras sem reimplementação:**
   - Adicionar coluna `criada_em` (audit trail)
   - Adicionar `atualizada_em` (soft updates)
   - Adicionar restrição de exclusividade em cenários multi-tenant

2. **Versionamento limpo:**
   - Separação entre "estrutura base" (M1) e "melhorias" (M2)
   - Facilita rollback seletivo se necessário

3. **Preparação para escalabilidade:**
   - Quando decisão de sharding for tomada, migration adicional pode particionar por `usuario_id`

**Mudança no Entendimento do Domínio:**

No design inicial, assumiu-se:
- ✅ Reservas são imutáveis após criação (não precisam de `updated_at`)
- ✅ Histórico é registrado em tabela separada (não precisa de audit column)

Se descoberta retroativa mostrasse que usuários editam reservas frequentemente, seria adicionada coluna `atualizada_em` em M2.

**Lição**: Migrações "vazias" são válidas e demonstram preparação arquitetural.

---

### 4. Race Conditions: Comportamento com Múltiplas Requisições Simultâneas

#### Cenário: Dois usuários tentam reservar o mesmo recurso no mesmo horário

```
T0: Usuario A faz GET /recursos/{id}  → recurso DISPONÍVEL
T1: Usuario B faz GET /recursos/{id}  → recurso DISPONÍVEL
T2: Usuario A faz POST /reservas       → cria Reserva A (14:00-15:00)
T3: Usuario B faz POST /reservas       → cria Reserva B (14:00-15:00) ← CONFLITO!
```

#### Decisão Implementada: **Otimistic Locking com Transações Serializable**

**Implementação:**

```python
# APP/repositories/reserva_repository.py
def verificar_sobreposicao_detalhado(db: Session, recurso_id, inicio, fim):
    # Query dentro da mesma transação do INSERT
    # Isolation Level garante que nenhuma reserva seja inserida entre CHECK e INSERT
    conflito = db.query(Reserva).filter(
        Reserva.recurso_id == recurso_id,
        Reserva.status.notin_([ReservaStatus.CANCELADA, ReservaStatus.REJEITADA]),
        Reserva.data_inicio < fim,
        Reserva.data_fim > inicio
    ).first()
    
    if not conflito:
        # INSERT executado na mesma transação
        db.add(nova_reserva)
        db.commit()  ← Atomicidade garantida
```

**Por que NOT usar Pessimistic Locking?**

| Abordagem | Implementação | Custo | Escalabilidade |
|-----------|---------------|-------|-----------------|
| **Pessimistic (LOCK FOR UPDATE)** | `SELECT ... FOR UPDATE` antes de INSERT | Alto (locks bloqueiam) | Ruim (contenção) |
| **Otimistic (transação + retry)** | Detecta conflito no COMMIT | Baixo (sem locks) | Bom (retry client-side) |

**Decisão: Otimistic** porque:
- ✅ Conflitos são raros (2 usuários na mesma hora em mesmo recurso → baixa probabilidade)
- ✅ Melhor throughput sob concorrência baixa/média
- ✅ Sem deadlocks

**Se tráfego fosse muito alto (100+ req/s no mesmo recurso):**
- Considerar Queue Pattern (Redis) + deduplicação
- Considerar Pessimistic com timeout curto

#### Comportamento Atual:

1. **Usuario A bem-sucedido**: Status 201, Reserva criada
2. **Usuario B**: Recebe `409 RESERVATION_CONFLICT` 
3. **Cliente B pode:**
   - Retry com horário diferente
   - Notificado via erro estruturado: `conflicting_period` mostra quando recurso está livre

**Sem implementação de race condition:**
- ❌ Ambos teriam sucesso (dados inconsistentes)
- ❌ Sistema aceitaria double-booking

---

### 5. Estados Terminais: Por que Não Retornar de Estados Terminais?

#### Máquina de Estados Definida

```
SOLICITADA ──→ CONFIRMADA ──→ EM_USO ──→ CONCLUIDA  [TERMINAL]
       ↓                                      ↑
       └──────────→ CANCELADA ─────────────┘  [TERMINAL]
       
       └──────────→ REJEITADA ────────────→ [TERMINAL]
```

#### Estados Terminais: `CONCLUIDA`, `CANCELADA`, `REJEITADA`

**Por que são terminais?**

| Estado | Razão de Ser Terminal |
|--------|----------------------|
| **CONCLUIDA** | Reserva foi usada e consumida. Recurso já foi entregue. Retornar seria "desfazer uso" → quebra invariante |
| **CANCELADA** | Usuário desistiu. Liberar novamente exigiria nova reserva. Sistema não permite "descancel" |
| **REJEITADA** | Admin rejeitou (motivo disciplinar, conflito, etc). Reaceptar exigiria override de decisão → auditoria |

**Invariantes violadas se permitissemos transições:**

1. **Concluída → Confirmada:**
   - Recurso foi entregue e usado por usuário
   - Permití-lo seria como "desconsumir" o recurso
   - Quebra histórico: `HistoricoStatusReserva` registraria evento impossível

2. **Cancelada → Ativa:**
   - Usuário cancelou com razão (não necessita mais)
   - Sistema não deve "surpresa" o usuário ativando sem novo pedido
   - Violaria consentimento implícito

3. **Rejeitada → Confirmada:**
   - Admin rejeitou por razão (ex.: usuário bloqueado, recurso indisponível)
   - Reaceptar sem anuência do admin é violação de autorização

**Implementação:**

```python
if novo_status == ReservaStatus.CANCELADA:
    if reserva.status != ReservaStatus.CONFIRMADA:
        raise InvalidStateTransitionException(...)
```

**Exceção levantada:**
```json
{
  "error": "INVALID_STATE_TRANSITION",
  "message": "Não é permitido transicionar de CONCLUIDA para CANCELADA.",
  "details": {
    "current_state": "CONCLUIDA",
    "requested_state": "CANCELADA"
  }
}
```

**Benefício:**
- ✅ Dados permanecem íntegros e auditáveis
- ✅ Comportamento previsível para clientes
- ✅ Facilita compliance e rastreamento

---

## 5.2 Consistência em Cenários de Borda

Cenários críticos identificados e decisões tomadas:

### Cenário 1: Deletar Usuário com Reservas Ativas

#### Problema
```sql
DELETE FROM usuario WHERE id = 'abc-123';
-- Mas esse usuário tem 2 reservas SOLICITADA e CONFIRMADA
```

#### Decisão: **Proibir Exclusão Sem Migração**

**Implementação (futura, não no scope atual):**

```python
@app.delete("/usuarios/{id}")
def deletar_usuario(id: UUID, db: Session):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    
    if not usuario:
        raise EntityNotFoundException("Usuario", str(id))
    
    # Verificar se tem reservas ativas
    reservas_ativas = db.query(Reserva).filter(
        Reserva.usuario_id == id,
        Reserva.status.in_([ReservaStatus.SOLICITADA, ReservaStatus.CONFIRMADA])
    ).count()
    
    if reservas_ativas > 0:
        raise BusinessRuleException(
            error_code="ACTIVE_RESERVATIONS_EXIST",
            message=f"Impossível deletar usuário: {reservas_ativas} reserva(s) ativa(s).",
            details={"active_count": reservas_ativas},
            status_code=409
        )
    
    # OK para deletar (histórico preservado em HistoricoStatusReserva)
    db.delete(usuario)
    db.commit()
```

**Por que não cascade delete?**
- ❌ Perderia histórico de quem fez a reserva
- ❌ Violaria auditoria (HistoricoStatusReserva orfã)
- ❌ Impossível rastrear cancelamentos posteriores

**Alternativa implementada:**
```python
# Soft delete (futuro)
usuario.status = UsuarioStatus.SUSPENSO
db.commit()
```

---

### Cenário 2: Recurso Limitado (Estoque/Vagas) Chegar a Zero

#### Problema
Imaginemos Recurso com campo `quantidade_disponivel`:
```
recurso = Recurso(nome="Livro X", quantidade_disponivel=3)
-- 3 usuários criam reservas (1 cada)
-- Quantidadeavailable = 0
-- 4º usuário tenta reservar
```

#### Decisão: **Validação no Serviço (RN-005 expandida)**

**Modelo atual (versão 1.0):**
- Recursos são entidades singleton (um único livro, uma única sala)
- Se alguém reserva, ninguém mais pode no mesmo período

**Se expandirmos para múltiplas cópias (versão 2.0):**

```python
@staticmethod
def criar_reserva(db: Session, dados_reserva: ReservaCreate) -> Reserva:
    # ... validações anteriores ...
    
    # Novo: verificar quantidade
    if hasattr(recurso, 'quantidade_disponivel'):
        em_uso = db.query(Reserva).filter(
            Reserva.recurso_id == recurso.id,
            Reserva.status.in_([ReservaStatus.EM_USO, ReservaStatus.CONFIRMADA]),
            # ... período sobreposto ...
        ).count()
        
        if em_uso >= recurso.quantidade_disponivel:
            raise BusinessRuleException(
                error_code="RESOURCE_EXHAUSTED",
                message="Recurso sem disponibilidade no período.",
                details={
                    "available": recurso.quantidade_disponivel,
                    "reserved": em_uso,
                    "request_quantity": 1
                },
                status_code=400
            )
```

**Decisão: Fila de Espera (futuro)**
- Em vez de erro, permitir reserva em estado `AGUARDANDO_DISPONIBILIDADE`
- Quando outra reserva é cancelada, sistema promove da fila

---

### Cenário 3: Modificar Entidade em Estado Terminal

#### Problema
```
PATCH /reservas/{id}/status
{
  "novo_status": "CONFIRMADA"  ← tentando "desconceluir"
}
-- Mas reserva está em estado CONCLUIDA
```

#### Decisão: **Rejeitar com Erro Específico**

**Implementação:**

```python
@staticmethod
def atualizar_status(db: Session, reserva_id: UUID, novo_status: ReservaStatus):
    reserva = ReservaRepository.buscar_por_id(db, reserva_id)
    
    TERMINAL_STATES = {ReservaStatus.CONCLUIDA, ReservaStatus.CANCELADA, ReservaStatus.REJEITADA}
    
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

**Benefício:**
- ✅ Cliente recebe feedback claro (em vez de silenciosamente ignorar)
- ✅ Auditoria: nenhum estado impossível é persistido

---

### Cenário 4: Datas/Horários Se Sobrepõem (RN-001 Edge Case)

#### Casos de Teste Implementados

```python
def test_sobreposicao_reserva_cancelada_nao_impede(client, db):
    """CANCELADA não bloqueia novos agendamentos"""
    # Cria reserva A: 14:00-16:00 (depois cancelada)
    # Cria reserva B: 14:30-15:30 ← deve ser permitido
    
def test_criar_reserva_sobreposicao(client, db):
    """CONFIRMADA bloqueia período"""
    # Cria reserva A: 14:00-16:00 (ativa)
    # Tenta reserva B: 14:30-15:30 ← deve ser bloqueado (409)

def test_criar_reserva_limite_aluno(client, db):
    """3ª reserva ativa permitida, 4ª bloqueada (RN-004)"""
```

#### Lógica Matemática

Duas reservas **se sobrepõem** se:

$$\text{reserva1.start} < \text{reserva2.end} \land \text{reserva1.end} > \text{reserva2.start}$$

**Implementação (SQL):**

```sql
SELECT * FROM reserva
WHERE recurso_id = $1
  AND status NOT IN ('CANCELADA', 'REJEITADA')  ← Exclui terminadas
  AND data_inicio < $3                            ← Antes do fim da nova
  AND data_fim > $2                               ← Depois do início da nova
LIMIT 1;
```

**Índice para Performance:**

```python
__table_args__ = (
    Index('idx_recurso_horario', 'recurso_id', 'data_inicio', 'data_fim'),
)
```

Busca em **O(log n)** em vez de **O(n)** full table scan.

---

### Cenário 5: Cálculo Derivado Fica Negativo/Inválido

#### Exemplo: Tempo Restante para Cancelamento

```python
tempo_restante = reserva.data_inicio - datetime.utcnow()
if tempo_restante < timedelta(hours=1):
    raise InsufficientNoticeCancellationException(...)
```

#### Edge Cases Tratados

| Cenário | Decisão |
|---------|---------|
| **Reserva com data no passado** | Bloqueia cancelamento (está acontecendo ou já aconteceu) |
| **data_fim < data_inicio** | Rejeita no Pydantic validator (erro 422) |
| **data_inicio == datetime.utcnow()** | Bloqueia cancelamento (< 1 hora) |
| **Timezone mismatch** | Usar UTC consistently (datetime.utcnow) |

**Implementação:**

```python
@model_validator(mode='after')
def verificar_horarios(self) -> 'ReservaCreate':
    if self.data_fim <= self.data_inicio:
        raise ValueError("A data de término deve ser estritamente posterior...")
    return self
```

---

## 5.3 Mensagens de Erro Informativas

### Estrutura Padronizada de Erro

Todos os erros seguem o padrão:

```json
{
  "error": "CÓDIGO_IDENTIFICADOR",
  "message": "Mensagem legível por humanos",
  "details": {
    "chave_contextual": "valor",
    "rule": "RN-XXX"  ← Para erros de negócio
  }
}
```

### Exemplos Implementados

#### RN-001: Sobreposição de Horário

**Request:**
```bash
POST /reservas/
{
  "usuario_id": "user-123",
  "recurso_id": "res-456",
  "data_inicio": "2024-03-15T14:00:00",
  "data_fim": "2024-03-15T16:00:00"
}
```

**Resposta (409 Conflict):**
```json
{
  "error": "RESERVATION_CONFLICT",
  "message": "Já existe uma reserva para este recurso no período solicitado.",
  "details": {
    "conflicting_period": {
      "start": "2024-03-15T14:30:00",
      "end": "2024-03-15T16:30:00"
    },
    "recurso_id": "res-456",
    "rule": "RN-001"
  }
}
```

**Benefício cliente:**
- ✅ Sabe exatamente qual período está ocupado
- ✅ Pode sugerir próximo slot disponível
- ✅ Identifica a regra violada

---

#### RN-002: Usuário Suspenso

**Response (403 Forbidden):**
```json
{
  "error": "USER_SUSPENDED",
  "message": "Sua conta possui pendências ou suspensões ativas.",
  "details": {
    "usuario_id": "user-789",
    "reason": "Pendências ou suspensões ativas",
    "rule": "RN-002"
  }
}
```

---

#### RN-003: Prazo Insuficiente

**Response (422 Unprocessable):**
```json
{
  "error": "INSUFFICIENT_NOTICE",
  "message": "Reservas só podem ser canceladas com antecedência mínima de 1 hora(s).",
  "details": {
    "reservation_start": "2024-03-15T15:00:00",
    "current_time": "2024-03-15T14:30:00",
    "minimum_hours": 1,
    "rule": "RN-003"
  }
}
```

---

#### RN-004: Limite Aluno Excedido

**Response (422 Unprocessable):**
```json
{
  "error": "STUDENT_LIMIT_EXCEEDED",
  "message": "Usuários do tipo ALUNO só podem possuir até 3 reservas ativas simultaneamente.",
  "details": {
    "usuario_id": "aluno-999",
    "current_active_reservations": 3,
    "limit": 3,
    "exceeding_by": 1,
    "rule": "RN-004"
  }
}
```

---

#### RN-005: Recurso Indisponível

**Response (400 Bad Request):**
```json
{
  "error": "RESOURCE_UNAVAILABLE",
  "message": "O recurso solicitado encontra-se em manutenção e não pode ser reservado.",
  "details": {
    "recurso_id": "res-xyz",
    "status": "MANUTENCAO",
    "resource_name": "Projetor Sala 301",
    "rule": "RN-005"
  }
}
```

---

#### Entidade Não Encontrada

**Response (404 Not Found):**
```json
{
  "error": "ENTITY_NOT_FOUND",
  "message": "Usuário não encontrado.",
  "details": {
    "entity_type": "Usuario",
    "entity_id": "user-does-not-exist"
  }
}
```

---

### Vantagens da Estrutura

| Aspecto | Benefício |
|---------|-----------|
| **Código de erro** | Enables i18n (frontend traduz `RESERVATION_CONFLICT`) |
| **Mensagem legível** | Usuário entende problema em português |
| **Details contextuais** | Integração com logging e debugging |
| **HTTP Status** | Protocolo correto (409 vs 422 vs 400) |
| **Rule ID** | Rastreabilidade em logs e auditorias |

---

## Resumo: Maturidade Arquitetural

| Aspecto | Status | Evidência |
|---------|--------|-----------|
| Relacionamentos justificados | ✅ | Sem denormalização excessiva; índices estratégicos |
| Separação de responsabilidades | ✅ | Validators em Pydantic; lógica em Service; dados em Repository |
| Tratamento de race conditions | ✅ | Transações serializable; erro 409 específico |
| Estados e terminais | ✅ | Máquina de estados enforçada; erro se terminal |
| Cenários de borda | ✅ | 5 cenários documentados + testes |
| Mensagens de erro | ✅ | Estruturadas com contexto; HTTP status corretos |
| Migrations versionadas | ✅ | Preparação para evolução; changelog claro |

**Conclusão**: Este design reflete maturidade de engenharia com decisões fundamentadas, tratamento robusto de edge cases e comunicação clara com clientes da API.

