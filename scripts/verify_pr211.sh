#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_TEST="$ROOT_DIR/backend/tests/test_plateau_fukuras_search.py"

claim() {
    printf '\n==> Claim: %s\n' "$1"
}

run() {
    printf '+ %s\n' "$*"
    "$@"
}

claim "repo hygiene: local Antigravity state is not tracked"
tracked_antigravity="$(git -C "$ROOT_DIR" ls-files | grep -E '(^|/)\.antigravitycli/' || true)"
tracked_existing_antigravity=""
while IFS= read -r path; do
    if [[ -n "$path" && -e "$ROOT_DIR/$path" ]]; then
        tracked_existing_antigravity="${tracked_existing_antigravity}${path}"$'\n'
    fi
done <<< "$tracked_antigravity"

if [[ -n "$tracked_existing_antigravity" ]]; then
    echo "Tracked .antigravitycli files still exist in the worktree. Remove them from the PR." >&2
    printf '%s' "$tracked_existing_antigravity" >&2
    exit 1
fi

claim "frontend package lock is consistent"
(
    cd "$FRONTEND_DIR"
    run npm install --package-lock-only --dry-run
)

claim "frontend production build works with Rspack 2 and PDF direct imports"
(
    cd "$FRONTEND_DIR"
    run npm run build
)

claim "frontend Jest suite passes"
(
    cd "$FRONTEND_DIR"
    run npm test -- --no-cache
)

claim "backend PLATEAU municipality regression tests pass in conda env paper-cad"
if ! command -v conda >/dev/null 2>&1; then
    echo "conda is required to run backend verification." >&2
    exit 1
fi

run conda run -n paper-cad python -m pytest "$BACKEND_TEST" -v

printf '\nAll PR #211 verification claims passed.\n'
