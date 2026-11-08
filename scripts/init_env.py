#!/usr/bin/env python3
"""Create deployment configuration without overwriting existing secrets."""
import argparse
import re
import secrets
from pathlib import Path

parser = argparse.ArgumentParser(description='Создать .env для сервера Кулис')
parser.add_argument('domain', help='Домен без https://, например events.example.ru')
args = parser.parse_args()
domain = args.domain.lower().strip().encode('idna').decode('ascii')
if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain):
    parser.error('Укажите доменное имя без протокола, порта и пути.')
root = Path(__file__).resolve().parent.parent
content = (root / '.env.example').read_text()
content = content.replace('events.example.ru', domain)
content = content.replace('replace-with-a-random-secret-of-at-least-50-characters', secrets.token_hex(32))
content = content.replace('replace-with-a-unique-database-password', secrets.token_hex(24))
try:
    fd = (root / '.env').open('x')
except FileExistsError:
    parser.exit(1, '.env уже существует. Он не изменён: сохраните существующие секреты.\n')
with fd:
    (root / '.env').chmod(0o600)
    fd.write(content)
print('.env создан, секреты сгенерированы. Заполните SMTP-параметры перед запуском.')
