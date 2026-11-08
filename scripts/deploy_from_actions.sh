#!/usr/bin/env bash
# Runs on a GitHub runner after the CI job succeeds.
set -euo pipefail

: "${DEPLOY_HOST:?Укажите DEPLOY_HOST в GitHub Actions Variables}"
: "${DEPLOY_USER:?Укажите DEPLOY_USER в GitHub Actions Variables}"
: "${DEPLOY_PATH:?Укажите DEPLOY_PATH в GitHub Actions Variables}"
: "${DEPLOY_SSH_KEY:?Укажите DEPLOY_SSH_KEY в GitHub Actions Secrets}"
: "${DEPLOY_KNOWN_HOSTS:?Укажите DEPLOY_KNOWN_HOSTS в GitHub Actions Secrets}"

# Limit characters passed into an SSH command and scp destination.
[[ "$DEPLOY_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || { echo 'Некорректный DEPLOY_HOST' >&2; exit 1; }
DEPLOY_PORT="${DEPLOY_PORT:-22}"
[[ "$DEPLOY_PORT" =~ ^[0-9]{1,5}$ ]] && (( DEPLOY_PORT >= 1 && DEPLOY_PORT <= 65535 )) || { echo 'Некорректный DEPLOY_PORT' >&2; exit 1; }
[[ "$DEPLOY_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || { echo 'Некорректный DEPLOY_USER' >&2; exit 1; }
[[ "$DEPLOY_PATH" =~ ^/[A-Za-z0-9_./-]+$ ]] || { echo 'Некорректный DEPLOY_PATH' >&2; exit 1; }
[[ "$DEPLOY_PATH" != *'..'* ]] || { echo 'DEPLOY_PATH не должен содержать ..' >&2; exit 1; }

umask 077
mkdir -p "$HOME/.ssh"
printf '%s\n' "$DEPLOY_SSH_KEY" > "$HOME/.ssh/kulisy_deploy"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$HOME/.ssh/known_hosts"
chmod 600 "$HOME/.ssh/kulisy_deploy" "$HOME/.ssh/known_hosts"
ssh-keygen -y -f "$HOME/.ssh/kulisy_deploy" >/dev/null
ssh_options=(-p "$DEPLOY_PORT" -i "$HOME/.ssh/kulisy_deploy" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=15)
remote="${DEPLOY_USER}@${DEPLOY_HOST}"

# First deployment is performed using DEPLOY.md so .env and the data volumes exist.
ssh "${ssh_options[@]}" "$remote" "test -f '$DEPLOY_PATH/.env' && test -x '$DEPLOY_PATH/scripts/backup.sh'"
scp -P "$DEPLOY_PORT" -i "$HOME/.ssh/kulisy_deploy" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=15 artifacts/kulisy-server.tar.gz "$remote:$DEPLOY_PATH/kulisy-server.tar.gz"
ssh "${ssh_options[@]}" "$remote" "cd '$DEPLOY_PATH' && ./scripts/backup.sh && tar -xzf kulisy-server.tar.gz --strip-components=1 && ./scripts/deploy.sh"
