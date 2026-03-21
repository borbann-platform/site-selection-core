#!/usr/bin/env bash
set -euo pipefail

dpkg-reconfigure --priority=low unattended-upgrades
systemctl enable unattended-upgrades
systemctl restart unattended-upgrades
systemctl status unattended-upgrades --no-pager
