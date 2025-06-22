#!/bin/bash
# Calculates releases for the last 8 weeks
/app/.venv/bin/python /app/manage.py calc_all_releases --first_to_calc "$(date -d "-3 weeks + $(( ( (3 - $(date  +%u)) % 7) + 1 )) days" +"%Y-%m-%d")"

/app/cron_scripts/refresh_views.sh
