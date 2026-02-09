#!/usr/bin/env bash
set -euo pipefail

MILESTONE_TITLE="v0.1.0"
EPIC_TITLE="epic: gml2step v0.1 delivery"

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 1
    }
}

ensure_label() {
    local name="$1"
    local color="$2"
    local description="$3"

    if gh api "repos/{owner}/{repo}/labels/${name}" >/dev/null 2>&1; then
        gh label edit "$name" --color "$color" --description "$description" >/dev/null
    else
        gh label create "$name" --color "$color" --description "$description" >/dev/null
    fi
}

ensure_milestone() {
    local existing
    existing="$(gh api "repos/{owner}/{repo}/milestones?state=all" --jq ".[] | select(.title==\"${MILESTONE_TITLE}\") | .title" | head -n1 || true)"
    if [[ -z "$existing" ]]; then
        gh api \
            -X POST \
            "repos/{owner}/{repo}/milestones" \
            -f title="${MILESTONE_TITLE}" \
            -f state="open" >/dev/null
    fi
}

find_issue_number_by_title() {
    local title="$1"
    gh issue list \
        --state all \
        --search "in:title \"${title}\"" \
        --json number,title \
        --jq ".[] | select(.title==\"${title}\") | .number" | head -n1 || true
}

create_issue_if_missing() {
    local title="$1"
    local body="$2"
    shift 2
    local labels=("$@")

    local issue_num
    issue_num="$(find_issue_number_by_title "$title")"
    if [[ -n "$issue_num" ]]; then
        echo "$issue_num"
        return
    fi

    local args=()
    for l in "${labels[@]}"; do
        args+=(--label "$l")
    done
    args+=(--milestone "${MILESTONE_TITLE}")

    local url
    url="$(gh issue create --title "$title" --body "$body" "${args[@]}")"
    echo "${url##*/}"
}

main() {
    require_cmd gh
    gh auth status >/dev/null

    ensure_label epic BFDADC "Top-level delivery tracking"
    ensure_label task 0E8A16 "Concrete implementation unit"
    ensure_label tracking 1D76DB "Cross-session progress tracking"
    ensure_label handoff F9D0C4 "Session handoff record"
    ensure_label blocked D73A4A "Blocked by dependency or decision"
    ensure_label release 5319E7 "Release-specific work"

    ensure_milestone

    local task1 task2 task3 task4 task5 task6 task7 epic

    task1="$(create_issue_if_missing \
        "task: scaffold gml2step repository" \
        "Create base package layout, pyproject, tests folder, and baseline docs." \
        task)"

    task2="$(create_issue_if_missing \
        "task: extract citygml core modules" \
        "Copy citygml modules and coordinate utilities, then replace imports to package-local paths." \
        task)"

    task3="$(create_issue_if_missing \
        "task: add public API wrappers" \
        "Expose convert/parse/stream_parse/extract_footprints as stable wrappers." \
        task)"

    task4="$(create_issue_if_missing \
        "task: add Typer CLI" \
        "Implement gml2step CLI commands for convert, parse, stream-parse, extract-footprints." \
        task)"

    task5="$(create_issue_if_missing \
        "task: add plateau optional module" \
        "Add optional plateau package and related data/modules behind optional dependency." \
        task)"

    task6="$(create_issue_if_missing \
        "task: add docker full-feature image" \
        "Provide OCCT-enabled Docker image and usage examples." \
        task)"

    task7="$(create_issue_if_missing \
        "task: add CI and release docs" \
        "Set up tests in CI and document release flow for package and Docker image." \
        task)"

    epic="$(create_issue_if_missing \
        "${EPIC_TITLE}" \
        "Parent tracking issue for gml2step v0.1 delivery." \
        epic tracking)"

    cat > /tmp/gml2step_epic_body.md <<EOF
Objective:
- Deliver standalone gml2step v0.1 (library + CLI + Docker).

Definition of done:
- Public API works: convert, parse, stream_parse, extract_footprints.
- CLI commands work.
- Docker full-feature mode works.
- Tests and docs are updated.

Child issues:
- [ ] #${task1} scaffold gml2step repository
- [ ] #${task2} extract citygml core modules
- [ ] #${task3} add public API wrappers
- [ ] #${task4} add Typer CLI
- [ ] #${task5} add plateau optional module
- [ ] #${task6} add docker full-feature image
- [ ] #${task7} add CI and release docs

Session handoff:
Last update: YYYY-MM-DD HH:MM UTC
Done:
- 
In progress:
- 
Next:
- 
Risks/Blockers:
- 
EOF

    gh issue edit "${epic}" --body-file /tmp/gml2step_epic_body.md >/dev/null

    echo "Created/updated issues for milestone ${MILESTONE_TITLE}:"
    echo "  Epic: #${epic}"
    echo "  Tasks: #${task1}, #${task2}, #${task3}, #${task4}, #${task5}, #${task6}, #${task7}"
}

main "$@"

