# gml2step v0.1 Issue Breakdown

This file is a ready-to-use issue plan so progress is visible even if a coding session ends unexpectedly.

## Recommended Setup
- Run bootstrap script once (requires `gh` auth):
  - `./scripts/bootstrap_gml2step_issues.sh`
- Create one Epic issue from `.github/ISSUE_TEMPLATE/gml2step-epic.yml`.
- Create task issues from `.github/ISSUE_TEMPLATE/gml2step-task.yml`.
- Link all task issues under the Epic issue using checkboxes.
- At session end, update `Session Handoff` in the Epic or open `session-handoff` issue.

## Milestone
- `v0.1.0`

## Suggested Labels
- `epic`
- `task`
- `tracking`
- `handoff`
- `blocked`
- `release`

## Epic
- `epic: gml2step v0.1 delivery`
  - Objective: standalone package with library + CLI + Docker.
  - Definition of done:
    - public API works (`convert`, `parse`, `stream_parse`, `extract_footprints`)
    - CLI commands work
    - Docker full-feature mode works
    - docs and tests are in place

## Task Issues (create in order)
1. `task: scaffold gml2step repository`
   - Deliverables:
     - package layout (`src/gml2step`, `tests`, `pyproject.toml`)
     - baseline README and license
   - Depends on: none

2. `task: extract citygml core modules`
   - Deliverables:
     - copy `backend/services/citygml/**`
     - copy `backend/services/coordinate_utils.py`
     - replace imports to package-local paths
   - Depends on: #1

3. `task: add public API wrappers`
   - Deliverables:
     - `convert`, `parse`, `stream_parse`, `extract_footprints`
     - stable return types and errors
   - Depends on: #2

4. `task: add Typer CLI`
   - Deliverables:
     - `gml2step convert`
     - `gml2step parse`
     - `gml2step stream-parse`
     - `gml2step extract-footprints`
   - Depends on: #3

5. `task: add plateau optional module`
   - Deliverables:
     - optional deps wiring (`gml2step[plateau]`)
     - copy and wire:
       - `backend/services/plateau_fetcher.py`
       - `backend/services/plateau_api_client.py`
       - `backend/utils/mesh_utils.py`
       - `backend/services/plateau_mesh_mapping.py`
       - `backend/data/mesh2_municipality.json`
   - Depends on: #1

6. `task: add docker full-feature image`
   - Deliverables:
     - Dockerfile with OCCT-enabled runtime
     - examples for conversion run
   - Depends on: #3

7. `task: add CI and release docs`
   - Deliverables:
     - tests in CI
     - packaging checks
     - release instructions (PyPI/TestPyPI + Docker tags)
   - Depends on: #3, #4, #6

## Session Update Template
Use this snippet in Epic comments:

```text
[Session Update] YYYY-MM-DD HH:MM UTC
Done:
- ...
In progress:
- ...
Next:
1. ...
2. ...
Blockers:
- ...
```
