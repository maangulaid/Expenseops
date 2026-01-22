# ExpenseOps Architecture

## System Overview

ExpenseOps is a distributed receipt processing system designed for scalability, reliability, and auditability. The system follows a microservices-inspired architecture with clear separation of concerns.

## High-Level Architecture

```
┌─────────────┐
│   React     │  Port 5173
│  Frontend   │  (Web UI)
└──────┬──────┘
       │ HTTP/REST
       ▼
┌──────────────┐
│   FastAPI    │  Port 8000
│     API      │  (Request Handler)
└──────┬───────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
┌──────────┐   ┌──────────┐
│PostgreSQL│   │  MinIO   │  Ports 9000-9001
│   DB     │   │ (Storage)│  (Object Storage)
└──────────┘   └──────────┘
       │
       │ Task Queue
       ▼
┌──────────────┐
│    Redis     │  Port 6379
│   (Broker)   │  (Message Queue)
└──────┬───────┘
       │
       │ Consume Tasks
       ▼
┌──────────────┐
│    Celery    │
│    Worker    │  (Background Processing)
└──────────────┘
```

## Components

### 1. API Service (FastAPI)

**Purpose**: Handle HTTP requests, authentication, and business orchestration

**Responsibilities**:
- User authentication (JWT)
- Request validation
- Receipt upload orchestration
- RBAC enforcement
- Task enqueuing
- API documentation (OpenAPI)

**Technology**: Python 3.11, FastAPI, SQLAlchemy, Alembic

**Endpoints**:
```
/api/v1/auth/*          - Authentication
/api/v1/receipts/*      - Receipt operations
/api/v1/policies/*      - Policy management (admin)
/api/v1/tickets/*       - Ticket management (support+)
/docs                   - Interactive API documentation
/health, /ready         - Health checks
```

### 2. Worker Service (Celery)

**Purpose**: Process receipts asynchronously with OCR and policy evaluation

**Responsibilities**:
- OCR text extraction (EasyOCR)
- Data parsing (merchant, amount, date)
- Policy evaluation
- State transitions
- Ticket creation on failures
- Retry logic with exponential backoff

**Technology**: Python 3.11, Celery, EasyOCR, PyTorch

**Processing Pipeline**:
```
1. Download from MinIO
2. OCR extraction (EasyOCR)
3. Parse structured data
4. Evaluate policies
5. Update status (COMPLETED/FLAGGED/FAILED)
6. Create audit events
```

### 3. Database (PostgreSQL)

**Purpose**: Persistent data storage with ACID guarantees

**Key Tables**:
- `users`, `roles`, `user_roles` - RBAC
- `receipts` - Receipt records with status
- `receipt_events` - Complete audit trail
- `policy_rules` - DB-driven policy configuration
- `policy_evaluations` - Policy check results
- `tickets` - Support tickets
- `idempotency_keys` - Request deduplication

**Key Features**:
- JSONB fields for metadata
- Optimized indexes
- Foreign key constraints
- Unique constraints for idempotency

### 4. Object Storage (MinIO)

**Purpose**: Store receipt images/PDFs

**Features**:
- S3-compatible API
- Safe key generation: `{user_id}/{uuid}_{timestamp}.{ext}`
- Automatic bucket creation
- Presigned URLs for temporary access

### 5. Message Broker (Redis)

**Purpose**: Task queue between API and Worker

**Features**:
- Persistent task storage
- Celery backend for results
- Queue: `receipts`

### 6. Frontend (React)

**Purpose**: Web interface for users

**Features**:
- Receipt upload
- Receipt list with status
- Login/authentication
- Responsive design

## Data Flow

### Receipt Upload Flow

```
1. User uploads file via Frontend/API
   │
   ├─ Validate file (type, size)
   ├─ Compute SHA256 hash
   └─ Check idempotency (user_id + hash)
       │
       ├─ If exists: Return existing receipt_id
       └─ If new:
           ├─ Upload to MinIO (safe key)
           ├─ Insert receipt (QUEUED)
           ├─ Create receipt_event
           ├─ Enqueue Celery task
           └─ Return 202 Accepted
```

### Worker Processing Flow

```
1. Celery worker picks up task
   │
   ├─ Transition: QUEUED → PROCESSING
   ├─ Create audit event
   │
2. Download file from MinIO
   │
3. OCR Extraction (EasyOCR)
   ├─ Extract raw text
   └─ Store in receipt.raw_ocr_text
   │
4. Data Parsing
   ├─ Extract merchant_name
   ├─ Extract total_amount
   ├─ Extract transaction_date
   └─ Calculate confidence_score
   │
5. Policy Evaluation
   ├─ Fetch active policy_rules
   ├─ Evaluate each rule
   ├─ Create policy_evaluations
   └─ If HIGH/CRITICAL violations:
       └─ Create tickets
   │
6. Final State
   ├─ If violations: FLAGGED
   ├─ If success: COMPLETED
   └─ If error: FAILED (after retries)
   │
7. Create audit event
```

### Retry Flow

```
Task Execution
   │
   ├─ Success → COMPLETED
   │
   └─ Failure
       ├─ Retry 1 (60s delay)
       ├─ Retry 2 (120s delay)
       ├─ Retry 3 (240s delay)
       │
       └─ Max Retries Exceeded
           ├─ Status → FAILED
           ├─ Create receipt_event
           └─ Create failure ticket
```

## State Machine

### Receipt Status Transitions

```
         ┌──────────┐
    ┌───▶│  QUEUED  │◀────┐
    │    └─────┬────┘     │
    │          │          │
    │          │ worker   │ reprocess
    │          ▼          │
    │    ┌────────────┐   │
    │    │PROCESSING  │   │
    │    └─────┬──────┘   │
    │          │          │
    │          ├──────────┼───┐
    │          │          │   │
    │          ▼          │   │
    │    ┌───────────┐   │   │
    └────│COMPLETED  │───┘   │
         └───────────┘       │
              ├──────────────┤
              ▼              ▼
         ┌─────────┐    ┌────────┐
         │ FLAGGED │────│ FAILED │
         └─────────┘    └────────┘
```

**Valid Transitions**:
- QUEUED → PROCESSING
- PROCESSING → COMPLETED
- PROCESSING → FLAGGED (policy violations)
- PROCESSING → FAILED (retry exhaustion)
- COMPLETED/FLAGGED/FAILED → QUEUED (reprocess)

**Enforcement**: State machine validates all transitions

## Security

### Authentication

- **JWT Tokens**: Access (15min) + Refresh (7 days)
- **Password Hashing**: bcrypt
- **Token Storage**: Client-side (localStorage)

### Authorization (RBAC)

**Roles**:
- **user**: Own receipts only
- **support**: All receipts, reprocess, tickets
- **admin**: Everything + policy management

**Enforcement**: Decorator-based at route level

```python
@require_role("admin", "support")
def reprocess_receipt(...):
    ...
```

### Data Security

- **Idempotency**: SHA256 hash prevents duplicates
- **Safe Keys**: UUID-based MinIO keys (no user input)
- **File Validation**: Type + size checks
- **SQL Injection**: Protected by SQLAlchemy ORM
- **CORS**: Configured origins only

## Observability

### Correlation ID

**Purpose**: Trace requests across services

**Flow**:
```
API Request (X-Correlation-ID header)
  → API logs
  → Celery task (passed as parameter)
  → Worker logs
  → Database events
  → API response (returned in header)
```

**Format**: UUID v4

### Structured Logging

**Format**: JSON

**Fields**:
- `timestamp`: ISO 8601
- `level`: DEBUG/INFO/WARNING/ERROR
- `logger`: Module name
- `message`: Log message
- `correlation_id`: Request correlation ID
- `exception`: Stack trace (if error)

**Example**:
```json
{
  "timestamp": "2026-01-15T12:34:56.789Z",
  "level": "INFO",
  "logger": "app.services.receipt_service",
  "message": "Receipt uploaded successfully",
  "correlation_id": "a7b3c2d1-e4f5-6789-abcd-ef0123456789",
  "receipt_id": 123
}
```

### Audit Trail

**Table**: `receipt_events`

**Captured Events**:
- upload_complete
- worker_start
- ocr_complete
- extraction_complete
- policy_flagged
- worker_complete
- failure
- reprocess_requested

**Query Example**:
```sql
SELECT * FROM receipt_events
WHERE receipt_id = 123
ORDER BY created_at;
```

## Scalability

### Horizontal Scaling

**API**: Multiple instances behind load balancer
- Stateless design
- JWT authentication (no sessions)
- Database connection pooling

**Worker**: Multiple instances per queue
- Task distribution via Redis
- Idempotent task execution
- No shared state

**Database**: Read replicas (future)
- Write to primary
- Read from replicas
- Connection pooling

### Performance Optimizations

**Database**:
- Indexes on common queries
- JSONB for flexible metadata
- Bulk operations where possible

**API**:
- Async route handlers
- Streaming file uploads
- 202 Accepted (don't wait for processing)

**Worker**:
- Concurrent workers (default: 2)
- Task prefetching
- Result expiration

## Reliability

### Retry Logic

**Configuration**:
- Max retries: 3
- Backoff: Exponential (60s, 120s, 240s)
- Jitter: Enabled

**Failure Handling**:
- Receipt → FAILED status
- Ticket created automatically
- Stack trace preserved

### Idempotency

**Upload**: Unique(user_id, source_sha256)
- Duplicate detection
- Return existing receipt_id
- 202 Accepted response

**Task Execution**:
- Skip already processed receipts
- No side effects on retry

### Health Checks

**Endpoints**:
- `/health`: Basic liveness
- `/ready`: Readiness (DB/Redis/MinIO)

**Docker**: Health check in compose

## Policy Engine

### DB-Driven Configuration

**Benefits**:
- Runtime configuration changes
- No code deployment needed
- Admin UI for management

**Policy Rules Table**:
```
id | code              | config                    | severity | is_active
---+-------------------+---------------------------+----------+-----------
1  | MAX_AMOUNT        | {"max_amount": 1000.00}  | HIGH     | true
2  | DUPLICATE_RECEIPT | {"look_back_days": 90}   | MEDIUM   | true
3  | MISSING_MERCHANT  | {"required": true}       | LOW      | true
```

### Policy Evaluation

**When**: After data extraction in worker

**Process**:
1. Fetch active policies
2. Evaluate each against receipt
3. Create policy_evaluations
4. If violations: Set FLAGGED status
5. If HIGH/CRITICAL: Create tickets

## Technology Stack

### Backend
- **Language**: Python 3.11
- **Framework**: FastAPI 0.109
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Task Queue**: Celery 5.3
- **OCR**: EasyOCR 1.7

### Database
- **RDBMS**: PostgreSQL 16
- **Broker**: Redis 7
- **Storage**: MinIO (S3-compatible)

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite 5
- **HTTP Client**: Axios

### Infrastructure
- **Container**: Docker Compose
- **Orchestration**: Docker Compose (dev)

## Deployment

### Development

```bash
docker compose up -d
```

**Services**:
- postgres (5432)
- redis (6379)
- minio (9000, 9001)
- api (8000)
- worker
- frontend (5173)

### Production Considerations

**Database**:
- Connection pooling
- Read replicas
- Automated backups
- Point-in-time recovery

**API**:
- Load balancer
- Multiple instances
- Rate limiting
- HTTPS/TLS

**Worker**:
- Auto-scaling based on queue depth
- Separate queues by priority
- Monitoring alerts

**Storage**:
- Bucket versioning
- Lifecycle policies
- CDN for presigned URLs

**Monitoring**:
- Prometheus + Grafana
- ELK/Loki for logs
- Sentry for errors
- Uptime checks

## Future Enhancements

### Phase 1
- Machine learning for extraction
- Multi-language OCR support
- Receipt categorization
- Expense reporting

### Phase 2
- Mobile app (React Native)
- Email receipt forwarding
- Slack/Teams integration
- Export to accounting software

### Phase 3
- Receipt validation (fraud detection)
- Approval workflows
- Budget tracking
- Analytics dashboard

## Appendix

### Environment Variables

See [.env.example](.env.example) for complete list

### API Documentation

Interactive docs: http://localhost:8000/docs

### Database Schema

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for detailed schema
