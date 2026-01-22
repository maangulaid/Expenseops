from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from datetime import datetime

Base = declarative_base()


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models."""

    @declared_attr
    def created_at(cls):
        return Column(DateTime, nullable=False, server_default=func.now())

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            nullable=False,
            server_default=func.now(),
            onupdate=func.now()
        )
