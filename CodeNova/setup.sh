#!/usr/bin/env bash
# One-time setup on Linux/macOS:  ./setup.sh
set -e
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')|; s|^SERVICE_API_KEY=.*|SERVICE_API_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')|" .env && rm -f .env.bak
  echo "Created .env - set ADMIN_EMAILS and SMTP details in it."
fi
if command -v docker >/dev/null; then docker compose up -d db; else
  sed -i.bak 's|^DATABASE_URL=postgresql.*|DATABASE_URL=sqlite:///./campus.db|' .env && rm -f .env.bak
  echo "Docker not found - using SQLite."
fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt -r video_service/requirements.txt -r backend/requirements-ml.txt
if grep -q '^VAPID_PUBLIC_KEY=$' .env; then
  keys=$(.venv/bin/python scripts/generate_vapid_keys.py)
  pub=$(echo "$keys" | grep PUBLIC); priv=$(echo "$keys" | grep PRIVATE)
  sed -i.bak "s|^VAPID_PUBLIC_KEY=.*|$pub|; s|^VAPID_PRIVATE_KEY=.*|$priv|" .env && rm -f .env.bak
fi
(cd video_service && ../.venv/bin/python download_weights.py) || true
(cd frontend && npm install)
echo "Setup finished. Start with: ./start.sh"
