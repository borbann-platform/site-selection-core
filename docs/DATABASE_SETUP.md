# Database Setup Guide

This guide covers setting up the database for the Borbann Real Estate Platform.

## Prerequisites

- PostgreSQL 14 or higher
- Python with `uv` package manager
- Database connection configured in `.env`

## Initial Setup

### 1. Configure Database Connection

Create a `.env` file in the `gis-server` directory with your database credentials:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/borbann_db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 2. Run Database Migrations

Navigate to the `gis-server` directory and run migrations:

```bash
cd gis-server
uv run alembic upgrade head
```

This will create all necessary tables including:
- Users and authentication tables
- Organizations and teams
- Permissions and roles
- Properties and valuations
- Audit logs and resource shares

### 3. Seed Default Permissions and Roles

After running migrations, seed the default permissions and roles:

```bash
cd gis-server
uv run python src/scripts/seed_permissions.py
```

This script is **idempotent** - you can safely run it multiple times without creating duplicates.

The script will create:
- **26 Permissions** covering all platform features
- **7 Default Roles**:
  - `system_admin` - Full system access
  - `org_owner` - Organization owner with full control
  - `org_admin` - Organization administrator
  - `org_member` - Basic organization member
  - `team_admin` - Team administrator
  - `team_member` - Team member with feature access
  - `viewer` - Read-only access

## Creating New Migrations

When you modify database models, create a new migration:

```bash
cd gis-server
uv run alembic revision --autogenerate -m "Description of changes"
```

Review the generated migration file in `gis-server/migrations/versions/` before applying it.

## Migration Commands

```bash
# Show current migration status
uv run alembic current

# Show migration history
uv run alembic history

# Upgrade to latest version
uv run alembic upgrade head

# Upgrade to specific version
uv run alembic upgrade <revision>

# Downgrade one version
uv run alembic downgrade -1

# Downgrade to specific version
uv run alembic downgrade <revision>
```

## Troubleshooting

### Migration Conflicts

If you encounter migration conflicts when working in a team:

1. Pull latest changes from the repository
2. Check current migration status: `uv run alembic current`
3. If there are conflicts, you may need to merge migration branches:
   ```bash
   uv run alembic merge heads -m "merge migrations"
   ```

### Resetting the Database

**⚠️ WARNING: This will delete all data**

To completely reset the database:

```bash
# Drop all tables
uv run alembic downgrade base

# Recreate all tables
uv run alembic upgrade head

# Reseed permissions and roles
uv run python src/scripts/seed_permissions.py
```

## Permission System

The platform uses Role-Based Access Control (RBAC) with the following structure:

### Permission Format

Permissions follow the format: `resource:action`

Examples:
- `property:read` - View properties
- `property:write` - Create/edit properties
- `valuation:run` - Run valuations
- `org:manage` - Manage organization settings

### Role Scopes

Roles can be assigned at different scopes:

1. **System** - System-wide roles (e.g., system_admin)
2. **Organization** - Organization-level roles (e.g., org_owner, org_admin)
3. **Team** - Team-level roles (e.g., team_admin, team_member)

### Custom Roles

Organization admins can create custom roles with specific permission combinations. System default roles cannot be modified or deleted.

## Default Permissions List

### Property Management
- `property:read`, `property:write`, `property:delete`, `property:export`

### Valuations
- `valuation:run`, `valuation:export`

### Analytics
- `analytics:read`, `analytics:export`

### AI Chat
- `chat:access`, `chat:export`

### Site Analysis
- `site:analyze`, `catchment:analyze`

### Location Intelligence
- `location:read`, `transit:read`

### Predictions
- `prediction:run`

### Projects
- `project:read`, `project:write`, `project:delete`

### Team Management
- `team:read`, `team:manage`, `team:invite`

### Organization Management
- `org:read`, `org:manage`, `org:billing`

### System Administration
- `system:admin`, `audit:read`

## Next Steps

After setting up the database:

1. Start the backend server: `uv run uvicorn main:app --reload`
2. Create your first user via the registration endpoint
3. Assign roles to users through the organization management API
4. Test the authentication flow

For API documentation, visit `http://localhost:8000/docs` when the server is running.
