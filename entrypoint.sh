#!/bin/bash
# Run-once rating calculation. Created on demand by rating-ui's RatingCalculationJob,
# which passes the date range as FIRST_RELEASE_DATE / LAST_RELEASE_DATE env vars.
# When a var is unset, calc_all_releases falls back to its own defaults
# (first release = tools.FIRST_NEW_RELEASE, last release = today).
set -euo pipefail

args=()
[[ -n "${FIRST_RELEASE_DATE:-}" ]] && args+=(--first_to_calc "$FIRST_RELEASE_DATE")
[[ -n "${LAST_RELEASE_DATE:-}" ]]  && args+=(--last_to_calc  "$LAST_RELEASE_DATE")

exec uv run /app/manage.py calc_all_releases "${args[@]}"
