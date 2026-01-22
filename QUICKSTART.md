# ExpenseOps - Quick Start Guide

This guide will get you up and running with ExpenseOps in less than 10 minutes.

## Prerequisites

- Docker & Docker Compose installed
- 8GB+ RAM recommended
- 10GB+ free disk space

## Step-by-Step Setup

### 1. Clone/Navigate to Project

```bash
cd "/Users/maan/Desktop/winter project /expenseops"
```

### 2. Create Environment File

```bash
cp .env.example .env
```

**IMPORTANT**: For production, change the following in `.env`:
- `SECRET_KEY` - Use a strong random string
- `POSTGRES_PASSWORD` - Change from default
- `MINIO_ROOT_PASSWORD` - Change from default

### 3. Start Infrastructure Services

Start PostgreSQL, Redis, and MinIO first:

```bash
docker compose up -d postgres redis minio createbuckets
```

Wait 30 seconds for services to be healthy:

```bash
# Check service status
docker compose ps

# All services should show "healthy"
```

### 4. Build and Start API

```bash
docker compose up -d --build api
```

This will:
- Build the API Docker image
- Run Alembic migrations (create all tables)
- Seed default roles and policies
- Create default admin user
- Start the FastAPI server on port 8000

**Check logs**:
```bash
docker compose logs -f api

# You should see:
# - "Alembic migrations completed"
# - "Default admin user created"
# - "Uvicorn running on http://0.0.0.0:8000"
```

### 5. Build and Start Worker

```bash
docker compose up -d --build worker
```

This will:
- Build the worker Docker image
- Start Celery worker listening on `receipts` queue

**Check logs**:
```bash
docker compose logs -f worker

# You should see:
# - "celery@... ready."
# - "Connected to redis://redis:6379/0"
```

### 6. Verify Services

```bash
# API health check
curl http://localhost:8000/health

# Expected: {"status":"healthy"}

# MinIO console
open http://localhost:9001
# Login: minioadmin / minioadmin_pw
# Verify bucket "receipts-raw" exists
```

### 7. Test the System

#### A. Get Access Token

```bash
# Login as default admin user
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@expenseops.local&password=Admin123!" \
  | jq -r '.access_token' > /tmp/token.txt

# Save token for subsequent requests
export TOKEN=$(cat /tmp/token.txt)
echo "Token: $TOKEN"
```

#### B. Upload a Test Receipt

Create a simple test image:

```bash
# Create a simple test receipt image (1x1 pixel)
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" | base64 -d > /tmp/test_receipt.png

# Upload it
curl -X POST http://localhost:8000/api/v1/receipts \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test_receipt.png" | jq .

# Expected response:
# {
#   "receipt_id": 1,
#   "status": "QUEUED",
#   "message": "Receipt uploaded and queued for processing",
#   "correlation_id": "..."
# }
```

#### C. Watch Worker Process Receipt

```bash
# Watch worker logs
docker compose logs -f worker

# You should see:
# - "Processing receipt 1"
# - "Starting OCR for receipt 1"
# - "Extraction complete"
# - "Receipt 1 processing complete: status=COMPLETED"
```

#### D. Check Receipt Status

```bash
# Get receipt details
curl http://localhost:8000/api/v1/receipts/1 \
  -H "Authorization: Bearer $TOKEN" | jq .

# Should show:
# {
#   "id": 1,
#   "status": "COMPLETED",  # or "PROCESSING" if still running
#   "merchant_name": "...",
#   "total_amount": ...,
#   ...
# }
```

#### E. View Audit Trail

```bash
# Get all events for the receipt
curl http://localhost:8000/api/v1/receipts/1/events \
  -H "Authorization: Bearer $TOKEN" | jq .

# Should show multiple events:
# - upload_complete
# - worker_start
# - ocr_complete
# - extraction_complete
# - worker_complete
```

### 8. API Documentation

Open interactive API docs:

```bash
open http://localhost:8000/docs
```

This shows all available endpoints with Try It Out functionality.

## Common Commands

### View All Logs

```bash
docker compose logs -f
```

### View Specific Service Logs

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f postgres
```

### Restart a Service

```bash
docker compose restart api
docker compose restart worker
```

### Run Migrations Manually

```bash
docker compose exec api alembic upgrade head
```

### Create Additional Admin User

```bash
docker compose exec api python -m app.scripts.create_admin \
  --email your@email.com \
  --password YourPassword123! \
  --full-name "Your Name"
```

### Access Database

```bash
docker compose exec postgres psql -U expenseops_user -d expenseops

# SQL commands:
# \dt              -- List tables
# SELECT * FROM receipts LIMIT 5;
# SELECT * FROM receipt_events ORDER BY created_at DESC LIMIT 10;
# \q               -- Exit
```

### Access Redis

```bash
docker compose exec redis redis-cli

# Redis commands:
# KEYS *           -- List all keys
# LLEN receipts    -- Check queue length
# exit             -- Exit
```

### Stop Everything

```bash
docker compose down
```

### Stop and Remove Volumes (Clean Slate)

```bash
docker compose down -v
```

## Troubleshooting

### API won't start

```bash
# Check logs
docker compose logs api

# Common issues:
# 1. Database not ready - wait 30s and retry
# 2. Port 8000 already in use - change in docker-compose.yml
```

### Worker not processing receipts

```bash
# Check worker logs
docker compose logs worker

# Check if worker is connected
docker compose exec redis redis-cli
> LLEN receipts  # Should show pending tasks

# Restart worker
docker compose restart worker
```

### Migration errors

```bash
# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d postgres
# Wait 30 seconds
docker compose up -d api
```

### MinIO connection issues

```bash
# Check MinIO is running
docker compose ps minio

# Check bucket exists
docker compose exec api python -c "
from app.services.storage_service import StorageService
s = StorageService()
print('MinIO connection OK')
"
```

## Next Steps

1. **Upload Real Receipts**: Use JPG/PNG receipt images
2. **Test Policy Engine**: Upload high-value receipt (>$1000) to see flagging
3. **Check Tickets**: Query `/api/v1/tickets` to see policy violations
4. **Reprocess Receipt**: Use `/api/v1/receipts/{id}/reprocess` endpoint
5. **Create Regular Users**: Register via `/api/v1/auth/register`
6. **Test RBAC**: Create support user and verify limited access

## Production Deployment

Before deploying to production:

1. Change all passwords in `.env`
2. Set strong `SECRET_KEY`
3. Use proper TLS/HTTPS
4. Configure persistent volumes
5. Set up backups (PostgreSQL + MinIO)
6. Configure monitoring (Prometheus + Grafana)
7. Review security settings
8. Scale workers based on load

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full production guide.

## Support

- API Documentation: http://localhost:8000/docs
- GitHub Issues: [Create an issue](https://github.com/yourorg/expenseops/issues)
- Full README: [README.md](README.md)
