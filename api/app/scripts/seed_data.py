"""
Seed database with initial data (if not exists).

Run after migrations: python -m app.scripts.seed_data
"""
from app.core.database import SessionLocal
from app.models.user import User, Role, UserRole
from app.core.security import hash_password
from app.core.logging import get_logger

logger = get_logger(__name__)


def seed_data():
    """Seed initial data if database is empty."""
    db = SessionLocal()

    try:
        # Check if roles exist (created by migration, but verify)
        roles_count = db.query(Role).count()
        if roles_count == 0:
            logger.warning("No roles found - they should have been created by migration")
            # Create roles manually
            roles = [
                Role(name="user", description="Regular user"),
                Role(name="support", description="Support staff"),
                Role(name="admin", description="Administrator")
            ]
            db.add_all(roles)
            db.commit()
            logger.info("Created default roles")

        # Check if admin user exists
        admin_email = "admin@expenseops.local"
        admin_user = db.query(User).filter(User.email == admin_email).first()

        if not admin_user:
            # Create default admin user
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password("Admin123!"),  # Change in production!
                full_name="System Administrator",
                is_active=True
            )
            db.add(admin_user)
            db.flush()

            # Assign admin role
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            if admin_role:
                user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
                db.add(user_role)

            db.commit()
            logger.info(f"Created default admin user: {admin_email}")
            print(f"\n{'='*60}")
            print(f"Default admin user created:")
            print(f"  Email: {admin_email}")
            print(f"  Password: Admin123!")
            print(f"  IMPORTANT: Change this password in production!")
            print(f"{'='*60}\n")
        else:
            logger.info("Admin user already exists")

        logger.info("Seed data complete")

    except Exception as e:
        logger.error(f"Error seeding data: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
