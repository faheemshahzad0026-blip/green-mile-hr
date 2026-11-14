#!/usr/bin/env bash
# On the server (example):
#   source /home/greenmil/virtualenv/hr.greenmilerecycling.com/3.12/bin/activate
#   cd /home/greenmil/hr.greenmilerecycling.com   # app root (contents of flask_app)
#   export DATABASE_URL='mysql+pymysql://USER:PASS%40WORD@HOST:3306/DB'
#   export SECRET_KEY='long-random-string'
#   # optional overrides:
#   export SUPER_ADMIN_USERNAME='U.Technologies'
#   export SUPER_ADMIN_PASSWORD='Admin@12345'
#   export AGENCY_ADMIN_USERNAME='Green-Mile-HR'
#   export AGENCY_ADMIN_PASSWORD='Green_Mile_HR@0112'
#   bash deploy_env.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"

: "${DATABASE_URL:?Set DATABASE_URL first}"
: "${SECRET_KEY:=change-this-to-a-long-random-string}"
: "${SUPER_ADMIN_USERNAME:=U.Technologies}"
: "${SUPER_ADMIN_PASSWORD:=Admin@12345}"
: "${SUPER_ADMIN_FULL_NAME:=U.Technologies}"
: "${AGENCY_NAME:=Green Mile}"
: "${AGENCY_COMPANY_NAME:=Green Mile Recycling LLC}"
: "${AGENCY_ADMIN_USERNAME:=Green-Mile-HR}"
: "${AGENCY_ADMIN_PASSWORD:=Green_Mile_HR@0112}"
: "${AGENCY_ADMIN_FULL_NAME:=Green Mile HR}"

cat > "$ENV_FILE" <<EOF
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=${DATABASE_URL}
SUPER_ADMIN_USERNAME=${SUPER_ADMIN_USERNAME}
SUPER_ADMIN_PASSWORD=${SUPER_ADMIN_PASSWORD}
SUPER_ADMIN_FULL_NAME=${SUPER_ADMIN_FULL_NAME}
AGENCY_NAME=${AGENCY_NAME}
AGENCY_COMPANY_NAME=${AGENCY_COMPANY_NAME}
AGENCY_ADMIN_USERNAME=${AGENCY_ADMIN_USERNAME}
AGENCY_ADMIN_PASSWORD=${AGENCY_ADMIN_PASSWORD}
AGENCY_ADMIN_FULL_NAME=${AGENCY_ADMIN_FULL_NAME}
EOF
chmod 600 "$ENV_FILE"
echo "Wrote $ENV_FILE"

cd "$ROOT"
export FLASK_APP=run.py
python - <<'PY'
from app import create_app
from app.extensions import db
from app.utils import ensure_seed_users

app = create_app()
with app.app_context():
    db.create_all()
    seeded = ensure_seed_users()
    sa = seeded["super_admin"]
    aa = seeded["agency_admin"]
    ag = seeded["agency"]
    print("DB ready.")
    print("  Super admin:", sa.username, "/", sa.full_name)
    print("  Agency:     ", ag.company_name, "(slug=%s)" % ag.slug)
    print("  Agency admin:", aa.username, "/", aa.full_name)
    print("  Logo path:  ", ag.logo_path)
PY
