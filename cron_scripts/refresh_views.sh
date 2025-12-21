#!/bin/bash
curl "https://rating.chgk.gg/recreate_views/b?token=${RATING_UI_TOKEN}"
curl "https://rating.chgk.gg/recalculate_truedl/b?token=${RATING_UI_TOKEN}"
curl "https://rating.chgk.gg/reset_cache?token=${RATING_UI_TOKEN}"
curl "https://rating.chgk.gg/b/players"
curl "https://rating.chgk.gg/b/tournaments"
