#!/usr/bin/env bash
set -euo pipefail

install -d /etc/fail2ban
cp deploy/config/fail2ban/jail.local /etc/fail2ban/jail.local
systemctl enable fail2ban
systemctl restart fail2ban
fail2ban-client status
