"""
Pytest configuration and fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import get_db
from app.models.base import Base
from app.models.user import User, Role, UserRole
from app.core.security import hash_password
from app.config import settings

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # Create roles
    roles = [
        Role(id=1, name="user", description="Regular user"),
        Role(id=2, name="support", description="Support staff"),
        Role(id=3, name="admin", description="Administrator")
    ]
    for role in roles:
        db.add(role)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Test User",
        is_active=True
    )
    db_session.add(user)
    db_session.flush()

    # Assign user role
    user_role = UserRole(user_id=user.id, role_id=1)  # user role
    db_session.add(user_role)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def test_admin(db_session):
    """Create a test admin user."""
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass123"),
        full_name="Admin User",
        is_active=True
    )
    db_session.add(user)
    db_session.flush()

    # Assign admin role
    admin_role = UserRole(user_id=user.id, role_id=3)  # admin role
    db_session.add(admin_role)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def user_token(client, test_user):
    """Get JWT token for test user."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "testpass123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def admin_token(client, test_admin):
    """Get JWT token for test admin."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_admin.email, "password": "adminpass123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(user_token):
    """Create auth headers for test user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token):
    """Create auth headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def sample_receipt_bytes():
    """Create a minimal PNG image for testing."""
    import base64
    # 1x1 pixel transparent PNG
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    return base64.b64decode(png_data)
