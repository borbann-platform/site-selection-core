# Production Deployment Runbook

This runbook adapts the current stack for a single-VPS production deployment with Docker Compose, host Nginx, Tailscale-only admin access, and GitHub Actions deployments through GHCR.

## Target Architecture

- Public traffic enters only through host Nginx on `80/443`.
- Application containers stay bound to loopback ports only.
- SSH, Postgres admin access, and Netdata stay on the Tailscale mesh.
- GitHub Actions joins Tailscale ephemerally per deploy, then exits.

## Minimum VPS Sizing

For this repository as it exists now, a realistic floor is higher than a typical small web app because PostGIS, Redis, MinIO, Python ML dependencies, and map/data workloads all coexist.

- Minimum pilot: `4 vCPU`, `8 GB RAM`, `160 GB SSD`, `2 GB swap`
- Safer production baseline: `6 vCPU`, `16 GB RAM`, `250 GB SSD`, `2-4 GB swap`
- If you plan to keep large runtime datasets or multiple model snapshots on-box, budget an extra `100-200 GB` storage headroom

## Why this floor

- Backend imports geospatial and ML packages that are memory-heavy during startup.
- PostGIS plus PgBouncer plus Redis plus MinIO add steady resident memory.
- Frontend is lightweight at runtime, but backend data/model mounts dominate storage.
- CI does not build on the VPS in this setup, but image pulls and container restarts still need free disk and RAM headroom.

## Repo Assets Added For Production

- `docker-compose.prod.yml`
- `frontend/Dockerfile.prod`
- `frontend/nginx.prod.conf`
- `gis-server/Dockerfile.prod`
- `deploy/env.production.example`
- `deploy/nginx/site-select-core.conf`
- `deploy/scripts/deploy.sh`
- `deploy/scripts/rollback.sh`
- `deploy/bootstrap/*.sh`
- `deploy/config/fail2ban/jail.local`
- `deploy/config/ssh/sshd_config.tailscale.conf`
- `deploy/config/netdata/netdata.conf`

## Fast Setup Path

If you want the quickest operator flow:

1. provision Ubuntu VPS
2. run bootstrap scripts from `deploy/bootstrap/`
3. install your SSH public key for the `deploy` user
4. verify Tailscale SSH works
5. move SSH to Tailscale-only
6. clone repo into `/opt/app`
7. create `/opt/app/.env.production`
8. copy runtime data/models into `/opt/app/runtime/gis-server/`
9. install host nginx config and issue Certbot certificate
10. add GitHub secrets and let CI/CD deploy

## Phase 1 - Harden the VPS

1. Update packages and create a non-root `deploy` user.
2. Lock SSH to key auth only.
3. Enable UFW with only `80/tcp`, `443/tcp`, and temporary `22/tcp`.
4. Add `2 GB` swap minimum.
5. Install Docker and Docker Compose plugin.
6. Configure Docker log rotation.

You can automate most of that with:

```bash
sudo bash deploy/bootstrap/01-base-system.sh
sudo bash deploy/bootstrap/02-docker.sh
```

## Phase 2 - Join Tailscale

Install Tailscale and advertise the VPS tag:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --advertise-tags=tag:vps
tailscale ip -4
```

After you verify Tailscale SSH works, bind SSH to the Tailscale IP only and remove public port 22 from UFW.

Helper:

```bash
sudo TAILSCALE_AUTHKEY=tskey-auth-xxxxx bash deploy/bootstrap/03-tailscale.sh
```

Then append the template from `deploy/config/ssh/sshd_config.tailscale.conf` into `/etc/ssh/sshd_config`, replacing `100.x.x.x` with the actual VPS Tailscale IP.

## Phase 3 - Prepare runtime files on the VPS

Clone the repo into `/opt/app` and prepare runtime state:

```bash
sudo mkdir -p /opt/app /opt/app/runtime/gis-server/data /opt/app/runtime/gis-server/models
sudo chown -R deploy:deploy /opt/app
git clone https://github.com/borbann-platform/site-selection-core.git /opt/app
cd /opt/app
cp deploy/env.production.example .env.production
```

Then edit `.env.production` with real values.

Important:

- put production secrets only in `.env.production`
- sync required runtime datasets into `runtime/gis-server/data`
- sync required trained models into `runtime/gis-server/models`

The production compose file intentionally mounts data/models from `runtime/` so the image stays smaller and deploys are code-focused.

Recommended layout:

```bash
/opt/app
  /.env.production
  /runtime/gis-server/data
  /runtime/gis-server/models
```

## Phase 4 - Build registry strategy

This repo now expects two GHCR images:

- backend: `ghcr.io/borbann-platform/site-selection-core-backend`
- frontend: `ghcr.io/borbann-platform/site-selection-core-frontend`

Both are tagged with the commit SHA in CI.

Note: the production backend image is heavy because `uv sync --no-dev` currently resolves ML and geospatial dependencies such as Torch, XGBoost, PyArrow, and related native libraries. Expect a long first build and a relatively large image unless the inference/runtime dependency set is reduced later.

## Phase 5 - Host Nginx and TLS

Use the template in `deploy/nginx/site-select-core.conf` as the host Nginx site.

Recommended flow:

1. install Nginx and Certbot
2. copy the config into `/etc/nginx/sites-available/site-select-core`
3. substitute `${APP_DOMAIN}`, `${APP_DOMAIN_WWW}`, `${FRONTEND_HOST_PORT}`, `${BACKEND_HOST_PORT}`
4. enable the site and validate with `nginx -t`
5. run Certbot for your domain

Bootstrap helper:

```bash
sudo APP_DOMAIN=example.com APP_DOMAIN_WWW=www.example.com CERTBOT_EMAIL=ops@example.com \
  bash deploy/bootstrap/07-certbot-nginx.sh
```

Only loopback ports should be published by Docker:

- frontend on `127.0.0.1:3000`
- backend on `127.0.0.1:8000`

## Phase 6 - Optional private operations services

If you want admin-only observability on the VPS:

- keep Netdata bound to the Tailscale IP only
- keep any direct Postgres access restricted to Tailscale
- do not publish Redis publicly

Suggested host-level Netdata binding:

```ini
[web]
    bind to = 100.x.x.x
```

You can copy `deploy/config/netdata/netdata.conf` and replace the placeholder IP with the VPS Tailscale address.

For direct SQL access from your laptop over Tailscale, `docker-compose.prod.yml` binds PgBouncer to `${TS_TAILSCALE_IP}:6432` only. Populate `TS_TAILSCALE_IP` in `.env.production` with the VPS Tailscale address.

## Phase 7 - GitHub Secrets

Add these repository secrets:

- `TAILSCALE_AUTHKEY`
- `VPS_TAILSCALE_IP`
- `VPS_DEPLOY_USER`
- `SSH_PRIVATE_KEY`
- `GHCR_USERNAME`
- `GHCR_TOKEN`
- `APP_HEALTHCHECK_URL`
- `SLACK_WEBHOOK` (optional)

Notes:

- prefer a PAT or fine-grained package token for VPS GHCR pulls instead of relying on `GITHUB_TOKEN`
- `APP_HEALTHCHECK_URL` should be your final public `https://.../healthz`

## Phase 8 - Deployment flow

The intended deploy order is:

1. test backend and frontend
2. build/push backend image
3. build/push frontend image
4. connect GitHub Actions runner to Tailscale
5. SSH to VPS over Tailscale
6. `git pull origin main`
7. log into GHCR on the VPS
8. `IMAGE_TAG=<sha> deploy/scripts/deploy.sh`
9. run public health check
10. if health check fails, run `deploy/scripts/rollback.sh`

The deploy workflow is also tightened to:

- serialize production deploys with GitHub Actions `concurrency`
- fail early if `.env.production` still contains `change-me`
- verify runtime data/model directories exist before deploy
- run local backend/frontend health checks on the VPS before marking success
- store only the last healthy image tag for simple rollback

## Phase 9 - First deployment checklist

- `docker compose --env-file .env.production -f docker-compose.prod.yml config`
- `docker compose --env-file .env.production -f docker-compose.prod.yml pull`
- `docker compose --env-file .env.production -f docker-compose.prod.yml up -d`
- `curl http://127.0.0.1:8000/healthz`
- `curl http://127.0.0.1:8000/readyz`
- `curl http://127.0.0.1:3000/healthz`
- `curl https://your-domain/healthz`

## Phase 10 - Backup guidance

At minimum, back up:

- Postgres data
- MinIO object storage if listing images matter in production
- `.env.production`
- runtime datasets/models manifests

Recommended approach:

- nightly `pg_dump` to object storage
- separate periodic file-level backup for `/opt/app/runtime` if it is authoritative

## Operational cautions

- Do not expose Postgres publicly.
- Do not expose MinIO console publicly unless you intentionally front it and lock it down.
- Keep model/data directories out of the built image unless you explicitly want huge image pushes.
- If readiness depends on mounted data/models, missing runtime files will show up only after container start, so validate mounts during first boot.
