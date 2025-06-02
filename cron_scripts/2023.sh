#!/bin/bash
# Calculates all 2023 releases
/app/.venv/bin/python /app/manage.py calc_all_releases --first_to_calc 2023-01-05 --last_to_calc 2023-12-28

/app/cron_scripts/refresh_views.sh
