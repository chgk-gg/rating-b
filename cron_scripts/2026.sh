#!/bin/bash
# Calculates all 2026 releases
uv run /app/manage.py calc_all_releases --first_to_calc 2026-01-01  --last_to_calc 2026-12-31

/app/cron_scripts/refresh_views.sh
