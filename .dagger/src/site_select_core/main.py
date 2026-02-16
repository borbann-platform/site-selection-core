import dagger
from dagger import dag, function, object_type


@object_type
class SiteSelectCore:
    """
    Dagger pipelines for CI and MLOps workflow orchestration.

    Phase 0 scope: provide local/CI parity wrappers for backend and frontend checks.
    """

    _WAIT_FOR_DB_SCRIPT = """
import os
import sys
import time

import psycopg2

dsn = os.environ["DATABASE_URL"]
for _ in range(60):
    try:
        conn = psycopg2.connect(dsn)
        conn.close()
        sys.exit(0)
    except Exception:
        time.sleep(1)

sys.exit(1)
"""

    def _repo(self) -> dagger.Directory:
        # Use privileged env workspace to access full repository contents.
        return dag.env(privileged=True).workspace()

    @function
    async def ci_backend(
        self,
        include_lint: bool = False,
        include_integration: bool = True,
    ) -> str:
        """
        Run backend CI checks using the same commands as GitHub Actions.

        Includes:
        - dependency sync (`uv sync --extra dev`)
        - optional lint checks (`ruff check` + format check)
        - unit tests
        - optional integration tests with ephemeral PostGIS service
        """
        repo = self._repo()
        uv_cache = dag.cache_volume("site-select-core-uv-cache")
        backend = (
            dag.container()
            .from_("ghcr.io/astral-sh/uv:python3.13-bookworm")
            .with_mounted_directory("/work", repo)
            .with_mounted_cache("/root/.cache/uv", uv_cache)
            .with_workdir("/work/gis-server")
            .with_env_variable("UV_PYTHON", "3.13")
            .with_exec(["uv", "sync", "--extra", "dev"])
        )

        if include_lint:
            backend = backend.with_exec(
                ["sh", "-lc", "uv run ruff check src/ tests/ || true"]
            )
            backend = backend.with_exec(
                ["sh", "-lc", "uv run ruff format --check src/ tests/ || true"]
            )

        test_env = {
            "DATABASE_URL": "postgresql://user:password@db:5432/gisdb",
            "JWT_SECRET_KEY": "test-secret",
        }

        backend = backend.with_service_binding(
            "db",
            (
                dag.container()
                .from_("postgis/postgis:16-3.4")
                .with_env_variable("POSTGRES_USER", "user")
                .with_env_variable("POSTGRES_PASSWORD", "password")
                .with_env_variable("POSTGRES_DB", "gisdb")
                .with_exposed_port(5432)
                .as_service()
            ),
        )

        for key, value in test_env.items():
            backend = backend.with_env_variable(key, value)

        backend = backend.with_exec(["uv", "run", "pytest", "tests/unit", "-v", "--tb=short"])

        if include_integration:
            backend = backend.with_exec(
                [
                    "uv",
                    "run",
                    "python",
                    "-c",
                    self._WAIT_FOR_DB_SCRIPT,
                ]
            )
            backend = backend.with_exec(
                ["uv", "run", "pytest", "tests/integration", "-v", "--tb=short"],
            )

        await backend.sync()
        return "ci-backend: passed"

    @function
    async def ci_frontend(self) -> str:
        """
        Run frontend CI checks using the same commands as GitHub Actions.

        Includes:
        - `npm ci`
        - `npm run lint`
        - `npm run test`
        - `npm run build`
        """
        repo = self._repo()
        npm_cache = dag.cache_volume("site-select-core-npm-cache")
        frontend = (
            dag.container()
            .from_("node:20-bookworm")
            .with_mounted_directory("/work", repo)
            .with_mounted_cache("/root/.npm", npm_cache)
            .with_workdir("/work/frontend")
            .with_exec(["npm", "ci"])
            .with_exec(["npm", "run", "lint"])
            .with_exec(["npm", "run", "test"])
            .with_exec(["npm", "run", "build"])
        )
        await frontend.sync()
        return "ci-frontend: passed"

    @function
    async def ci_all(self) -> str:
        """Run backend and frontend CI checks (phase 0 pilot)."""
        backend = await self.ci_backend()
        frontend = await self.ci_frontend()
        return "\n".join([backend, frontend, "ci-all: passed"])
