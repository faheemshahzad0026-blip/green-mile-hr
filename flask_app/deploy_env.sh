#!/usr/bin/env bash
# On the server:
#   source /home/greenmil/virtualenv/hr.greenmilerecycling.com/3.12/bin/activate
#   cd /home/greenmil/hr.greenmilerecycling.com/flask_app   # or your app root
#   export DATABASE_URL='mysql+pymysql://USER:PASS%40WORD@HOST:3306/DB'
#   export SUPER_ADMIN_USERNAME='Green-Mile-HR'
#   export SUPER_ADMIN_PASSWORD='...'
#   export SUPER_ADMIN_FULL_NAME='U.Technologies'
#   export SECRET_KEY='...'
#   bash deploy_env.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"

: "${DATABASE_URL:?Set DATABASE_URL first}"
: "${SUPER_ADMIN_USERNAME:=Green-Mile-HR}"
: "${SUPER_ADMIN_PASSWORD:?Set SUPER_ADMIN_PASSWORD first}"
: "${SUPER_ADMIN_FULL_NAME:=U.Technologies}"
: "${SECRET_KEY:=change-this-to-a-long-random-string}"

cat > "$ENV_FILE" <<EOF
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=${DATABASE_URL}
SUPER_ADMIN_USERNAME=${SUPER_ADMIN_USERNAME}
SUPER_ADMIN_PASSWORD=${SUPER_ADMIN_PASSWORD}
SUPER_ADMIN_FULL_NAME=${SUPER_ADMIN_FULL_NAME}
EOF
chmod 600 "$ENV_FILE"
echo "Wrote $ENV_FILE"

cd "$ROOT"
export FLASK_APP=run.py
python - <<'PY'
from app import create_app
from app.extensions import db
from app.utils import ensure_super_admin

app = create_app()
with app.app_context():
    db.create_all()
    user = ensure_super_admin()
    print("DB ready. Super admin:", user.username, "/", user.full_name)
PY
