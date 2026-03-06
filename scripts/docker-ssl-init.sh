#!/bin/sh
set -eu

docker compose up -d nginx
docker compose run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d "${FASTAPI_CFG__SITE__DOMAIN}" \
  -d "www.${FASTAPI_CFG__SITE__DOMAIN}" \
  --email "${LETSENCRYPT_EMAIL}" \
  --agree-tos \
  --no-eff-email

docker compose restart nginx
