#!/bin/bash
curl "https://rating.chgk.gg/recreate_views/b?token=${RATING_UI_TOKEN}" > /dev/null 2>&1
curl "https://rating.chgk.gg/recalculate_truedl/b?token=${RATING_UI_TOKEN}" > /dev/null 2>&1
curl "https://rating.chgk.gg/reset_cache?token=${RATING_UI_TOKEN}" > /dev/null 2>&1
curl "https://rating.chgk.gg/b/players" > /dev/null 2>&1
curl "https://rating.chgk.gg/b/tournaments" > /dev/null 2>&1
