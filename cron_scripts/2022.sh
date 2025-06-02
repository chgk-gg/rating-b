#!/bin/bash
# Calculates all 2022 releases
/app/.venv/bin/python /app/manage.py calc_all_releases --first_to_calc 2022-01-06 --last_to_calc 2022-12-29

/app/cron_scripts/refresh_views.sh
