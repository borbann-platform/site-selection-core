#!/usr/bin/env bash
set -euo pipefail

APP_DOMAIN="${APP_DOMAIN:?APP_DOMAIN is required}"
APP_DOMAIN_WWW="${APP_DOMAIN_WWW:-}"
EMAIL="${CERTBOT_EMAIL:?CERTBOT_EMAIL is required}"

snap install core
snap refresh core
snap install --classic certbot
ln -sf /snap/bin/certbot /usr/bin/certbot

certbot --nginx \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  -d "$APP_DOMAIN" \
  $( [[ -n "$APP_DOMAIN_WWW" ]] && printf '%s' "-d $APP_DOMAIN_WWW" )

certbot renew --dry-run
