import datetime
from typing import Dict, List, Iterable
from django.db.models import F, Q
from django.db import connection
import logging
import pandas as pd
from b import models
from .constants import SCHEMA_NAME

logger = logging.getLogger(__name__)


def fast_insert(table: str, data: Iterable[dict], batch_size: int = 5000):
    """
    Inserts data from all dicts in an iterable.
    :param table: table to be updated
    :param data: iterable of uniform dicts
    :param batch_size: max number of rows to be inserted in a single query
    :return:
    """
    data_iter = iter(data)

    try:
        first_item = next(data_iter)
    except StopIteration:
        return

    columns = first_item.keys()
    columns_joined = ", ".join(columns)

    with connection.cursor() as cursor:
        batch = [first_item]
        for row in data_iter:
            batch.append(row)
            if len(batch) >= batch_size:
                values = ",\n".join(f"({','.join(str(row[column]) for column in columns)})" for row in batch)
                cursor.execute(f"INSERT INTO {SCHEMA_NAME}.{table} ({columns_joined}) VALUES {values}")
                batch = []

        # Process remaining rows in the final batch
        if batch:
            values = ",\n".join(f"({','.join(str(row[column]) for column in columns)})" for row in batch)
            cursor.execute(f"INSERT INTO {SCHEMA_NAME}.{table} ({columns_joined}) VALUES {values}")


def get_season(release_date: datetime.date) -> models.Season:
    return models.Season.objects.get(start__lte=release_date, end__gte=release_date)


def get_base_teams_for_players(release_date: datetime.date) -> pd.Series:
    season = get_season(release_date)
    base_teams = (
        season.season_roster_set.filter(
            Q(start_date__lte=release_date),
            Q(end_date=None) | Q(end_date__gt=release_date),
        )
        .annotate(base_team_id=F("team_id"))
        .values("player_id", "base_team_id", "start_date")
    )
    bs_pd = pd.DataFrame(base_teams)
    return bs_pd.sort_values("start_date").groupby("player_id").last().base_team_id.astype("Int64")


def get_teams_with_new_players(old_release: datetime.date, new_release: datetime.date) -> List[int]:
    return list(
        models.Season_roster.objects.filter(start_date__gt=old_release, start_date__lte=new_release)
        .values_list("team_id", flat=True)
        .distinct()
    )


def get_tournament_end_dates() -> Dict[int, datetime.date]:
    return {
        tournament["pk"]: tournament["end_datetime"].date()
        for tournament in models.Tournament.objects.all().values("pk", "end_datetime")
    }


def get_dead_players(date) -> set[int]:
    return set(
        models.Player.objects.filter(date_died__lte=date).values_list("id", flat=True)
    )
