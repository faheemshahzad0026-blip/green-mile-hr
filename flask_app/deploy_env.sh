#!/usr/bin/env bash
# On the server:
#   source ~/virtualenv/hr.greenmilerecycling.com/3.12/bin/activate
#   cd ~/hr.greenmilerecycling.com
#   export DATABASE_URL='mysql+pymysql://greenmil_hr_app_database:greenmil_hr_app_database%400336@127.0.0.1:3306/greenmil_hr_app_database'
#   bash deploy_env.sh
#
# Admin users are NOT written to .env — flask init-db / ensure_seed_users inserts them into MySQL.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"

: "${DATABASE_URL:?Set DATABASE_URL first}"
: "${SECRET_KEY:=green-mile-hr-prod-secret-change-if-needed}"

cat > "$ENV_FILE" <<EOF
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=${DATABASE_URL}
EOF
chmod 600 "$ENV_FILE"
echo "Wrote $ENV_FILE (DB + secret only)"

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
    print("DB ready — users seeded in database:")
    print("  Super admin:", sa.username)
    print("  Agency:     ", ag.company_name, "(slug=%s)" % ag.slug)
    print("  Agency admin:", aa.username)
    print("  Logo path:  ", ag.logo_path)
PY
