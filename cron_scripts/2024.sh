#!/bin/bash
# Calculates all 2024 releases
/app/.venv/bin/python /app/manage.py calc_all_releases --first_to_calc 2024-01-04 --last_to_calc 2024-12-26

/app/cron_scripts/refresh_views.sh
