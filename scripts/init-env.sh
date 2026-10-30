#! /usr/bin/env sh

# Creates .env from .env.copy, filling every secret left empty in the template
# with a freshly generated random value. .env is gitignored; .env.copy must stay
# free of credentials.

set -e

SECRETS="FIRST_SUPERUSER_PASSWORD POSTGRES_PASSWORD S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY"

FORCE=false
if [ "$1" = "--force" ]; then
  FORCE=true
fi

if [ -f .env ] && [ "$FORCE" = false ]; then
  echo ".env already exists, leaving it untouched (use --force to regenerate)." >&2
  exit 0
fi

random_secret() {
  if command -v openssl > /dev/null 2>&1; then
    openssl rand -hex 16
  else
    head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

cp .env.copy .env

for name in $SECRETS; do
  # Only fill the ones the template leaves empty, never overwrite a set value.
  if grep -q "^${name}=$" .env; then
    value=$(random_secret)
    sed -i.bak "s|^${name}=$|${name}=${value}|" .env
    rm -f .env.bak
  fi
done

echo "Wrote .env with generated secrets for: $SECRETS"
