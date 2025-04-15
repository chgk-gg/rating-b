import datetime
import time
from typing import Dict, List, Iterable
from django.db.models import F, Q
from django.db import connection
import logging
import pandas as pd
from io import StringIO
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
                values = ",\n".join(
                    f'({",".join(str(row[column]) for column in columns)})'
                    for row in batch
                )
                cursor.execute(
                    f"INSERT INTO {SCHEMA_NAME}.{table} ({columns_joined}) VALUES {values}"
                )
                batch = []

        # Process remaining rows in the final batch
        if batch:
            values = ",\n".join(
                f'({",".join(str(row[column]) for column in columns)})' for row in batch
            )
            cursor.execute(
                f"INSERT INTO {SCHEMA_NAME}.{table} ({columns_joined}) VALUES {values}"
            )


def bulk_insert_copy(
    table: str, data: Iterable[dict], batch_size: int = 50000
):
    """
    Fast bulk insert using PostgreSQL's COPY command.

    Args:
        table: Table name to insert into
        data: Iterable of dictionaries with data to insert
        batch_size: Number of rows per batch

    Returns:
        Total number of records inserted
    """
    total_start_time = time.time()
    total_rows = 0

    # Function to convert string "NULL" to None
    def normalize_nulls(row):
        return {k: None if v == "NULL" else v for k, v in row.items()}

    data_iter = iter(data)
    try:
        batch = []
        for _ in range(min(batch_size, 1000)):
            try:
                item = next(data_iter)
                batch.append(normalize_nulls(item))
            except StopIteration:
                break

        if not batch:
            return 0

        columns = list(batch[0].keys())

    except StopIteration:
        return 0

    with connection.cursor() as cursor:
        cursor.execute("BEGIN")
        try:
            # Process batches with NULL handling
            def process_batch(batch):
                batch_df = pd.DataFrame(batch)
                buffer = StringIO()
                batch_df[columns].to_csv(
                    buffer,
                    index=False,
                    header=False,
                    sep="\t",
                    na_rep="\\N",
                    quoting=None,
                )
                buffer.seek(0)
                return buffer

            # Process first batch
            buffer = process_batch(batch)
            batch_start_time = time.time()
            cursor.copy_from(
                file=buffer, table=table, columns=columns, null="\\N"
            )

            batch_size_actual = len(batch)
            total_rows += batch_size_actual
            batch_time = time.time() - batch_start_time

            logger.info(
                f"Inserted {batch_size_actual} rows into {table} in {batch_time:.2f} seconds "
                f"({batch_size_actual / batch_time:.1f} rows/sec)"
            )

            # Process remaining batches
            while True:
                batch = []
                for _ in range(batch_size):
                    try:
                        item = next(data_iter)
                        batch.append(normalize_nulls(item))
                    except StopIteration:
                        break

                if not batch:
                    break

                batch_start_time = time.time()
                buffer = process_batch(batch)

                cursor.copy_from(
                    file=buffer, table=table, columns=columns, null="\\N"
                )

                batch_size_actual = len(batch)
                total_rows += batch_size_actual
                batch_time = time.time() - batch_start_time

                logger.info(
                    f"Inserted {batch_size_actual} rows into {table} in {batch_time:.2f} seconds "
                    f"({batch_size_actual / batch_time:.1f} rows/sec)"
                )

            cursor.execute("COMMIT")

        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error during bulk insert with COPY: {str(e)}")
            raise

    total_time = time.time() - total_start_time
    logger.info(
        f"Bulk insert complete: {total_rows} rows inserted into {table} in {total_time:.2f} seconds "
        f"({total_rows / total_time:.1f} rows/sec)"
    )

    return total_rows


def get_season(release_date: datetime.date) -> models.Season:
    return models.Season.objects.get(start__lte=release_date, end__gte=release_date)


def get_base_teams_for_players(release_date: datetime.date) -> pd.Series:
    season = get_season(release_date)
    base_teams = (
        season.season_roster_set.filter(
            Q(start_date=None) | Q(start_date__lte=release_date),
            Q(end_date=None) | Q(end_date__lte=release_date),
        )
        .annotate(base_team_id=F("team_id"))
        .values("player_id", "base_team_id", "start_date")
    )
    bs_pd = pd.DataFrame(base_teams)
    return (
        bs_pd.sort_values("start_date")
        .groupby("player_id")
        .last()
        .base_team_id.astype("Int64")
    )


def get_teams_with_new_players(
    old_release: datetime.date, new_release: datetime.date
) -> List[int]:
    return list(
        models.Season_roster.objects.filter(
            start_date__gt=old_release, start_date__lte=new_release
        )
        .values_list("team_id", flat=True)
        .distinct()
    )


def get_tournament_end_dates() -> Dict[int, datetime.date]:
    return {
        tournament["pk"]: tournament["end_datetime"].date()
        for tournament in models.Tournament.objects.all().values("pk", "end_datetime")
    }
