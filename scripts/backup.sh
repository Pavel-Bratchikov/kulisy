#!/usr/bin/env bash
# Run daily on the deployment host, for example with cron. Keep backups in Russia.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_file="backups/kulisy-${backup_stamp}.dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${backup_file}.partial"
mv "${backup_file}.partial" "$backup_file"
# Include locally stored receipts. When S3 is enabled this archive can be empty;
# configure bucket versioning/backup separately in that case.
media_file="backups/kulisy-${backup_stamp}-media.tar.gz"
docker compose exec -T web python -c 'import sys, tarfile; archive = tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz"); archive.add("/app/media", arcname="media"); archive.close()' > "${media_file}.partial"
mv "${media_file}.partial" "$media_file"
# Install AWS CLI on the host; supply credentials via its standard environment.
# BACKUP_S3_URI and S3_ENDPOINT_URL must point to the chosen Russian storage.
if [ -n "${BACKUP_S3_URI:-}" ]; then
    aws --endpoint-url "$S3_ENDPOINT_URL" s3 cp "$backup_file" "${BACKUP_S3_URI%/}/"
    aws --endpoint-url "$S3_ENDPOINT_URL" s3 cp "$media_file" "${BACKUP_S3_URI%/}/"
fi
printf 'Backups saved: %s and %s\n' "$backup_file" "$media_file"
