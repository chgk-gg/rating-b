#!/bin/bash
# Calculates all 2025 releases
/app/.venv/bin/python /app/manage.py calc_all_releases --first_to_calc 2025-01-02

/app/cron_scripts/refresh_views.sh
