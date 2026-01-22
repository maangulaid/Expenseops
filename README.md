# ExpenseOps

> A production-ready receipt processing system with OCR, policy enforcement, and comprehensive audit trails.

## Overview

ExpenseOps is a full-stack application that automates receipt processing using OCR technology, enforces configurable business policies, and maintains complete audit trails for compliance and debugging. Built with modern technologies and designed for scalability.

## Features

- **Idempotent Upload**: Duplicate receipts are automatically detected (SHA256 hash)
- **Automated OCR**: Extract merchant name, amount, date using EasyOCR
- **Policy Engine**: DB-driven rules (max amount, duplicate detection, required fields)
- **State Machine**: Comprehensive status tracking (QUEUED → PROCESSING → COMPLETED/FLAGGED/FAILED)
- **Audit Trail**: Every state transition recorded with correlation ID
- **RBAC**: Role-based access control (user, support, admin)
- **Retry Logic**: Exponential backoff with automatic ticket creation on failure
- **Observability**: Structured JSON logging with request tracing

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic
- **Worker**: Celery, EasyOCR
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Storage**: MinIO (S3-compatible)
- **Frontend**: React 18, Vite, TypeScript
- **Container**: Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Python 3.11+, Node 18+ for local development

### 1. Clone and Setup

```bash
# Navigate to project directory
cd expenseops

# Copy environment template
cp .env.example .env

# (Optional) Edit .env for custom configuration
```

### 2. Start All Services

```bash
# Build and start all containers
docker compose up -d

# Watch logs
docker compose logs -f
```

Services will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:5173
- **MinIO Console**: http://localhost:9001
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Run Database Migrations

```bash
# Run migrations
docker compose exec api alembic upgrade head

# Verify current migration
docker compose exec api alembic current
```

### 4. Create Admin User

```bash
docker compose exec api python -m app.scripts.create_admin \
  --email admin@example.com \
  --password Admin123!
```

### 5. Access the Application

Open http://localhost:5173 in your browser and login with:
- Email: `admin@example.com`
- Password: `Admin123!`

## 3-Minute Demo Script

```bash
# 1. Login as admin and get token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin@example.com&password=Admin123!" \
  | jq -r '.access_token' > /tmp/admin_token

# 2. Upload a receipt
curl -X POST http://localhost:8000/api/v1/receipts \
  -H "Authorization: Bearer $(cat /tmp/admin_token)" \
  -F "file=@sample_receipt.jpg" \
  | jq .

# 3. Watch worker process the receipt
docker compose logs -f worker

# 4. Check receipt details (replace 1 with actual receipt_id)
curl http://localhost:8000/api/v1/receipts/1 \
  -H "Authorization: Bearer $(cat /tmp/admin_token)" \
  | jq .

# 5. View audit trail
curl http://localhost:8000/api/v1/receipts/1/events \
  -H "Authorization: Bearer $(cat /tmp/admin_token)" \
  | jq .

# 6. Update policy threshold (admin only)
curl -X PATCH http://localhost:8000/api/v1/policies/1 \
  -H "Authorization: Bearer $(cat /tmp/admin_token)" \
  -H "Content-Type: application/json" \
  -d '{"config": {"max_amount": 500.00}}'

# 7. Upload high-value receipt (should get FLAGGED)
curl -X POST http://localhost:8000/api/v1/receipts \
  -H "Authorization: Bearer $(cat /tmp/admin_token)" \
  -F "file=@expensive_receipt.jpg"

# 8. Check tickets created by policy violations
curl http://localhost:8000/api/v1/tickets \
  -H "Authorization: Bearer $(cat /tmp/admin_token)" \
  | jq .
```

## Architecture

### System Components

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   React     │────▶│   FastAPI    │────▶│  PostgreSQL  │
│  Frontend   │     │     API      │     │   Database   │
└─────────────┘     └──────────────┘     └──────────────┘
                           │
                           │ Enqueue Task
                           ▼
                    ┌──────────────┐     ┌──────────────┐
                    │    Redis     │────▶│    Celery    │
                    │   (Broker)   │     │    Worker    │
                    └──────────────┘     └──────────────┘
                                                │
                                                │ Store File
                                                ▼
                                         ┌──────────────┐
                                         │    MinIO     │
                                         │   (Storage)  │
                                         └──────────────┘
```

### Receipt Processing Flow

1. **Upload** (API): Validate → Hash → Idempotency Check → MinIO Upload → DB Insert → Enqueue
2. **Process** (Worker): Download → OCR → Extract Data → Evaluate Policies → Update Status
3. **Audit**: Every transition creates a `receipt_events` record with correlation_id
4. **Policy**: Violations result in FLAGGED status and support tickets

### State Machine

```
QUEUED ──▶ PROCESSING ──▶ COMPLETED
                │
                ├─────────▶ FLAGGED (policy violation)
                │
                └─────────▶ FAILED (retry exhaustion)
                                │
                                └─────▶ Ticket Created

All states can transition back to QUEUED via reprocess endpoint
```

## Development

### Run API Locally

```bash
cd api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://expenseops_user:expenseops_password@localhost:5432/expenseops
export CELERY_BROKER_URL=redis://localhost:6379/0

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload
```

### Run Worker Locally

```bash
cd worker
source venv/bin/activate
pip install -r requirements.txt

# Start worker
celery -A app.celery_app worker --loglevel=info --queues=receipts
```

### Run Frontend Locally

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
# API tests
docker compose run api pytest -v

# Worker tests
docker compose run worker pytest -v

# With coverage
docker compose run api pytest --cov=app --cov-report=html
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info

### Receipts
- `POST /api/v1/receipts` - Upload receipt
- `GET /api/v1/receipts` - List receipts (RBAC filtered)
- `GET /api/v1/receipts/{id}` - Get receipt details
- `GET /api/v1/receipts/{id}/events` - Get audit trail
- `POST /api/v1/receipts/{id}/reprocess` - Reprocess (support+)

### Policies (Admin Only)
- `GET /api/v1/policies` - List policy rules
- `POST /api/v1/policies` - Create policy rule
- `PATCH /api/v1/policies/{id}` - Update policy config
- `DELETE /api/v1/policies/{id}` - Deactivate policy

### Tickets (Support+)
- `GET /api/v1/tickets` - List tickets
- `GET /api/v1/tickets/{id}` - Get ticket details
- `PATCH /api/v1/tickets/{id}` - Update ticket status

Full API documentation: http://localhost:8000/docs

## Configuration

Key environment variables in `.env`:

```bash
# Database
POSTGRES_DB=expenseops
POSTGRES_USER=expenseops_user
POSTGRES_PASSWORD=expenseops_password

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
S3_BUCKET_RECEIPTS_RAW=receipts-raw

# JWT
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# File Upload
MAX_UPLOAD_SIZE_MB=10
ALLOWED_FILE_TYPES=image/jpeg,image/png,application/pdf

# Celery
CELERY_MAX_RETRIES=3
CELERY_RETRY_BACKOFF_BASE=60
```

## Testing & Evaluation

### Run Test Suite

```bash
# All tests
docker compose run api pytest -v

# Specific test categories
docker compose run api pytest tests/test_api/test_idempotency.py -v
docker compose run api pytest tests/test_services/test_state_machine.py -v
```

### Run Evaluation Harness

```bash
cd evaluation

# Prepare ground truth data
# (Add receipt images to ground_truth/receipts/ and expected JSON to ground_truth/expected/)

# Run evaluation
python harness.py \
  --ground-truth ./ground_truth \
  --api-url http://localhost:8000/api/v1 \
  --token $ADMIN_TOKEN

# View results
cat reports/report_*.json | jq .
```

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment guide.

### Production Checklist

- [ ] Change all default passwords in `.env`
- [ ] Set strong `SECRET_KEY` for JWT
- [ ] Configure HTTPS/TLS for API
- [ ] Enable PostgreSQL backups
- [ ] Configure MinIO with persistent volume
- [ ] Set up log aggregation (ELK/Loki)
- [ ] Configure monitoring (Prometheus + Grafana)
- [ ] Scale workers based on load
- [ ] Review and tune database indexes
- [ ] Enable rate limiting on API

## Troubleshooting

### Database Connection Issues

```bash
# Check Postgres is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Connect directly
docker compose exec postgres psql -U expenseops_user -d expenseops
```

### Worker Not Processing

```bash
# Check worker logs
docker compose logs worker

# Check Redis connection
docker compose exec redis redis-cli ping

# Manually enqueue task
docker compose exec api python -c "from app.tasks.celery_app import celery_app; celery_app.send_task('app.tasks.process_receipt.process_receipt_task', args=[1, 'test-corr-id'])"
```

### MinIO Access Issues

```bash
# Check MinIO health
curl http://localhost:9000/minio/health/live

# Access MinIO console
open http://localhost:9001

# Check bucket exists
docker compose exec api python -c "from app.services.storage_service import StorageService; s = StorageService(); print('Buckets OK')"
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and data flow
- [API Reference](docs/API_REFERENCE.md) - Detailed endpoint documentation
- [Deployment](docs/DEPLOYMENT.md) - Production deployment guide
- [Runbook](docs/RUNBOOK.md) - Operational procedures

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run full test suite
5. Submit pull request

## Support

For issues and questions:
- GitHub Issues: [github.com/yourorg/expenseops/issues](https://github.com/yourorg/expenseops/issues)
- Documentation: [docs/](docs/)
- Email: support@example.com
