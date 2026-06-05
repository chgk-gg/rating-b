#!/bin/bash
# Calculates all 2025 releases
uv run /app/manage.py calc_all_releases --first_to_calc 2025-01-02 --last_to_calc 2025-12-25

/app/cron_scripts/refresh_views.sh
