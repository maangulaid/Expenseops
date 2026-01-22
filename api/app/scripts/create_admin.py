"""
Create an admin user via command line.

Usage: python -m app.scripts.create_admin --email admin@example.com --password MyPassword123!
"""
import argparse
from app.core.database import SessionLocal
from app.models.user import User, Role, UserRole
from app.core.security import hash_password
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_admin_user(email: str, password: str, full_name: str = None):
    """Create an admin user."""
    db = SessionLocal()

    try:
        # Check if user exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.error(f"User with email {email} already exists")
            print(f"ERROR: User with email {email} already exists")
            return False

        # Create user
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True
        )
        db.add(user)
        db.flush()

        # Assign admin role
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            logger.error("Admin role not found in database")
            print("ERROR: Admin role not found. Run migrations first.")
            return False

        user_role = UserRole(user_id=user.id, role_id=admin_role.id)
        db.add(user_role)

        db.commit()

        logger.info(f"Admin user created: {email}")
        print(f"\n{'='*60}")
        print(f"Admin user created successfully:")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        print(f"  Role: admin")
        print(f"{'='*60}\n")

        return True

    except Exception as e:
        logger.error(f"Error creating admin user: {e}", exc_info=True)
        db.rollback()
        print(f"ERROR: {e}")
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--full-name", help="User full name")

    args = parser.parse_args()

    # Validate password strength
    if len(args.password) < 8:
        print("ERROR: Password must be at least 8 characters")
        return

    success = create_admin_user(args.email, args.password, args.full_name)

    if not success:
        exit(1)


if __name__ == "__main__":
    main()
