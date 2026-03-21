# Deploy Helpers

This folder contains production deployment templates and one-time VPS bootstrap helpers.

Suggested order on a fresh VPS:

1. `deploy/bootstrap/01-base-system.sh`
2. `deploy/bootstrap/02-docker.sh`
3. `deploy/bootstrap/03-tailscale.sh`
4. `deploy/bootstrap/04-firewall.sh`
5. `deploy/bootstrap/05-fail2ban.sh`
6. `deploy/bootstrap/06-unattended-upgrades.sh`
7. `deploy/bootstrap/07-certbot-nginx.sh`

Then:

1. clone repo into `/opt/app`
2. copy `deploy/env.production.example` to `/opt/app/.env.production`
3. sync runtime data into `/opt/app/runtime/gis-server/data`
4. sync runtime models into `/opt/app/runtime/gis-server/models`
5. install host nginx config from `deploy/nginx/site-select-core.conf`
6. run the GitHub Actions deploy workflow or deploy manually with `IMAGE_TAG=<tag> APP_ENV_FILE=/opt/app/.env.production bash deploy/scripts/deploy.sh`

Helpful deploy toggles:

- `APP_IMAGE_PULL_POLICY=missing` keeps manually loaded app images usable on first deploys while still pulling future missing tags from GHCR
- `RUN_APP_BOOTSTRAP=1` runs the idempotent database bootstrap before the final app rollout
- `ROLLBACK_PULL_POLICY=missing` lets rollback pull an older tag only when it is not already present locally
