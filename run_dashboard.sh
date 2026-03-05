#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Keep bytecode cache local to the project to avoid permission issues.
export PYTHONPYCACHEPREFIX="$SCRIPT_DIR/.pycache"

MISSING_PACKAGES="$(python3 - <<'PY'
import importlib.util

required = ["streamlit", "pandas", "openpyxl"]
missing = [pkg for pkg in required if importlib.util.find_spec(pkg) is None]
print(" ".join(missing))
PY
)"

if [[ -n "${MISSING_PACKAGES}" ]]; then
  echo "Instalando dependencias faltantes: ${MISSING_PACKAGES}"
  python3 -m pip install --user ${MISSING_PACKAGES}
fi

exec python3 -m streamlit run app.py "$@"
