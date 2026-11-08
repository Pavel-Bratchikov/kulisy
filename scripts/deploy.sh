#!/usr/bin/env bash
# Uses COMPOSE_FILE when configured for an existing reverse proxy.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
    echo 'Сначала выполните: python3 scripts/init_env.py YOUR_DOMAIN и настройте SMTP в .env' >&2
    exit 1
fi
# Validate without displaying the resolved secrets.
docker compose config --quiet
docker compose build
docker compose run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
docker compose run --rm --no-deps web python manage.py check_server_config
docker compose up -d --wait --wait-timeout 180
docker compose ps
echo 'Контейнеры запущены. Проверьте HTTPS, письмо с билетом и фото чека по инструкции DEPLOY.md.'
