"""
Seed script to populate default permissions and roles in the database.

This script is idempotent - it can be safely run multiple times.
It will create missing permissions/roles but won't duplicate existing ones.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.database import SessionLocal
from src.models.permission import DEFAULT_PERMISSIONS, DEFAULT_ROLES, Permission, Role


def seed_permissions(db: Session) -> dict[str, Permission]:
    """
    Seed default permissions into the database.

    Returns a dict mapping permission names to Permission objects.
    """
    print("🌱 Seeding permissions...")

    permissions_map: dict[str, Permission] = {}
    created_count = 0

    for name, resource, action, description in DEFAULT_PERMISSIONS:
        # Check if permission already exists
        existing = db.execute(
            select(Permission).where(Permission.name == name)
        ).scalar_one_or_none()

        if existing:
            permissions_map[name] = existing
            print(f"  ✓ Permission '{name}' already exists")
        else:
            permission = Permission(
                name=name,
                resource=resource,
                action=action,
                description=description,
            )
            db.add(permission)
            permissions_map[name] = permission
            created_count += 1
            print(f"  + Created permission '{name}'")

    db.commit()

    # Refresh all permissions to get IDs
    for perm in permissions_map.values():
        db.refresh(perm)

    print(
        f"✅ Permissions seeded: {created_count} created, {len(DEFAULT_PERMISSIONS) - created_count} already existed\n"
    )
    return permissions_map


def seed_roles(db: Session, permissions_map: dict[str, Permission]) -> None:
    """
    Seed default system roles into the database.

    Only creates system-level default roles (organization_id=None, is_system_default=True).
    """
    print("🌱 Seeding default roles...")

    created_count = 0

    for role_name, role_config in DEFAULT_ROLES.items():
        # Check if role already exists
        existing = db.execute(
            select(Role).where(
                Role.name == role_name,
                Role.is_system_default == True,  # noqa: E712
                Role.organization_id.is_(None),
            )
        ).scalar_one_or_none()

        if existing:
            print(f"  ✓ Role '{role_name}' already exists")
            # Update permissions if needed
            existing_perm_names = {p.name for p in existing.permissions}
            required_perm_names = set(role_config["permissions"])

            if existing_perm_names != required_perm_names:
                print(f"    ↻ Updating permissions for '{role_name}'")
                existing.permissions = [
                    permissions_map[perm_name]
                    for perm_name in role_config["permissions"]
                ]
                db.commit()
                print(f"    ✓ Permissions updated for '{role_name}'")
        else:
            # Create new role
            role = Role(
                name=role_name,
                scope=role_config["scope"],
                description=role_config["description"],
                is_system_default=True,
                organization_id=None,  # System-wide role
            )

            # Assign permissions
            role.permissions = [
                permissions_map[perm_name] for perm_name in role_config["permissions"]
            ]

            db.add(role)
            created_count += 1
            print(
                f"  + Created role '{role_name}' with {len(role_config['permissions'])} permissions"
            )

    db.commit()
    print(
        f"✅ Roles seeded: {created_count} created, {len(DEFAULT_ROLES) - created_count} already existed\n"
    )


def main() -> None:
    """Main entry point for the seed script."""
    print("\n" + "=" * 60)
    print("🚀 Starting permission and role seeding...")
    print("=" * 60 + "\n")

    db = SessionLocal()
    try:
        # Seed permissions first
        permissions_map = seed_permissions(db)

        # Then seed roles with their permissions
        seed_roles(db, permissions_map)

        print("=" * 60)
        print("✅ Seeding completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
