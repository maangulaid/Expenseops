from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "expenseops",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "app.tasks.process_receipt.process_receipt_task": {"queue": "receipts"}
    },
    result_expires=3600,
)
