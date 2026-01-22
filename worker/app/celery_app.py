from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "expenseops_worker",
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

    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Task routing
    task_routes={
        "app.tasks.process_receipt.process_receipt_task": {"queue": "receipts"}
    },

    # Result expiration
    result_expires=3600,
)


# Signal handlers for correlation tracking
@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extra):
    """Log task start with correlation ID."""
    correlation_id = kwargs.get('correlation_id') or args[1] if len(args) > 1 else 'N/A'
    logger.info(
        f"Task {task.name} starting",
        extra={"task_id": task_id, "correlation_id": correlation_id}
    )


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, **extra):
    """Log task completion."""
    correlation_id = kwargs.get('correlation_id') or args[1] if len(args) > 1 else 'N/A'
    logger.info(
        f"Task {task.name} completed",
        extra={"task_id": task_id, "correlation_id": correlation_id}
    )


@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, **extra):
    """Log task failure."""
    correlation_id = kwargs.get('correlation_id') or args[1] if len(args) > 1 else 'N/A'
    logger.error(
        f"Task failed: {exception}",
        extra={
            "task_id": task_id,
            "correlation_id": correlation_id,
            "exception": str(exception),
            "traceback": traceback
        }
    )


# Import tasks to register them
from app.tasks import process_receipt  # noqa
