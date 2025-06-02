#!/bin/bash
# Calculates all 2021 releases
/app/.venv/bin/python /app/manage.py calc_all_releases --first_to_calc 2021-09-09 --last_to_calc 2021-12-30

/app/cron_scripts/refresh_views.sh
