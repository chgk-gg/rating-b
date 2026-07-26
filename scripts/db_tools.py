import datetime
import decimal
import logging
from collections.abc import Iterable
from functools import cache

import pandas as pd
from django.apps import apps
from django.db import connection
from django.db.models import F, Q

from b import models

from .constants import SCHEMA_NAME

logger = logging.getLogger(__name__)

# Rows are canonicalized to exactly what Postgres will store before they are either
# hashed (changes.fingerprint) or inserted (fast_insert): floats bound for integer or
# decimal columns carry extra precision that the column type discards, and a release
# fingerprint computed from that extra precision differs on sub-storage float jitter,
# forcing rewrites of releases whose stored rows are unchanged.
# Rounding matches Postgres's numeric -> integer/numeric(n) cast (ties away from
# zero, not to even), which is how these values were rounded when the cast did it.
# Uses an explicit context so the precision is independent of any global decimal state.
_ROUNDING_CONTEXT = decimal.Context(prec=28)

_INTEGER_FIELD_TYPES = {
    "AutoField",
    "BigAutoField",
    "SmallAutoField",
    "IntegerField",
    "BigIntegerField",
    "SmallIntegerField",
    "PositiveIntegerField",
    "PositiveBigIntegerField",
    "PositiveSmallIntegerField",
}


def round_half_away(value) -> int:
    return int(
        decimal.Decimal(str(value)).quantize(
            decimal.Decimal(1), rounding=decimal.ROUND_HALF_UP, context=_ROUNDING_CONTEXT
        )
    )


@cache
def _fields_by_column(table: str) -> dict:
    model = next(model for model in apps.get_models() if model._meta.db_table == table)
    return {field.column: field for field in model._meta.fields}


def canonicalize_row(table: str, row: dict) -> dict:
    fields = _fields_by_column(table)

    def canonicalize(column, value):
        # Strings are SQL fragments like "NULL"/"TRUE"; leave them (and unknown columns) alone.
        if isinstance(value, str) or value is None or column not in fields:
            return value
        field = fields[column]
        target = field.target_field if field.is_relation else field
        internal_type = target.get_internal_type()
        if internal_type in _INTEGER_FIELD_TYPES:
            return round_half_away(value)
        if internal_type == "DecimalField":
            return decimal.Decimal(str(value)).quantize(
                decimal.Decimal(1).scaleb(-target.decimal_places, context=_ROUNDING_CONTEXT),
                rounding=decimal.ROUND_HALF_UP,
                context=_ROUNDING_CONTEXT,
            )
        return value

    return {column: canonicalize(column, value) for column, value in row.items()}


def fast_insert(table: str, data: Iterable[dict], batch_size: int = 5000):
    """
    Inserts data from all dicts in an iterable, canonicalized to the column types.
    :param table: table to be updated
    :param data: iterable of uniform dicts
    :param batch_size: max number of rows to be inserted in a single query
    :return:
    """
    data_iter = (canonicalize_row(table, row) for row in data)

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
    return (
        bs_pd.sort_values(["start_date", "base_team_id"], kind="stable")  # base_team_id breaks ties
        .groupby("player_id")
        .last()
        .base_team_id.astype("Int64")
    )


def get_teams_with_new_players(old_release: datetime.date, new_release: datetime.date) -> list[int]:
    return list(
        models.Season_roster.objects.filter(start_date__gt=old_release, start_date__lte=new_release)
        .values_list("team_id", flat=True)
        .distinct()
    )


def get_tournament_end_dates() -> dict[int, datetime.date]:
    return {
        tournament["pk"]: tournament["end_datetime"].date()
        for tournament in models.Tournament.objects.all().values("pk", "end_datetime")
    }
