import datetime
import decimal
import sys
import pandas as pd
import numpy as np
import logging
from django.utils import timezone
from typing import Iterable, List, Tuple
from dotenv import load_dotenv
from django.db import connection, transaction

from b import models

from . import db_tools
from . import tools
from . import tournament as trnmt
from .teams import TeamRating
from .players import PlayerRating
from .changes import fingerprint
from .constants import SCHEMA_NAME

load_dotenv()

logger = logging.getLogger(__name__)

decimal.getcontext().prec = 1


# Reads the teams rating for given release_id.
def get_team_rating(release_id: int) -> TeamRating:
    teams_list = list(
        models.Team_rating.objects.filter(release_id=release_id)
        .values("team_id", "rating", "trb", "place")
        .order_by("-rating")
    )
    return TeamRating(teams_list=teams_list)


# Calculates new teams and players rating based on old rating and provided set of tournaments.
def make_step_for_teams_and_players(
    initial_teams: TeamRating,
    initial_players: PlayerRating,
    tournaments: Iterable[trnmt.Tournament],
    new_release: models.Release,
) -> Tuple[TeamRating, PlayerRating]:
    existing_player_ids = set(initial_players.data.index)
    new_player_ids = set()
    for tournament in tournaments:
        logger.debug(
            f"Tournament {tournament.id}..." + ("" if tournament.is_in_maii_rating else " (not in MAII rating)")
        )
        initial_teams.add_new_teams(tournament, initial_players)
        tournament.add_ratings(initial_teams, initial_players)
        tournament.calc_bonuses(initial_teams)
        new_player_ids |= tournament.get_new_player_ids(existing_player_ids)

    logger.info("Calculated tournament ratings")
    final_teams = initial_teams.copy()
    final_players = initial_players.copy()
    if new_player_ids:
        new_players = (
            pd.DataFrame(({"player_id": player_id, "rating": 0, "top_bonuses": []} for player_id in new_player_ids))
            .set_index("player_id")
            .join(db_tools.get_base_teams_for_players(new_release.date), how="left")
        )
        final_players.data = pd.concat([final_players.data, new_players])

    logger.info("Added new players")

    # We need these columns to dump the difference between new and old rating.
    final_teams.data["prev_rating"] = final_teams.data["rating"]
    final_players.data["prev_rating"] = final_players.data["rating"]

    final_players.reduce_rating()
    for tournament in tournaments:
        if tournament.is_in_maii_rating:
            final_teams, final_players = tournament.apply_bonuses(final_teams, final_players)
    logger.info("Applied bonuses")
    # Team rating cannot be negative.
    final_teams.data["rating"] = np.maximum(final_teams.data["rating"], 0)
    final_players.recalc_rating()
    logger.info("Recalculated players rating")
    return final_teams, final_players


# The build_* functions below produce the exact rows that would be written for a
# release. They are used both to fingerprint the release (to decide whether the
# write can be skipped) and, when it cannot, as the payload for fast_insert.


def delete_previous_results(release_id):
    with connection.cursor() as cursor:
        cursor.execute(f"delete from {SCHEMA_NAME}.player_rating where release_id = {release_id}")
        cursor.execute(f"delete from {SCHEMA_NAME}.team_rating where release_id = {release_id}")
        cursor.execute(f"delete from {SCHEMA_NAME}.player_rating_by_tournament where release_id = {release_id}")
        cursor.execute(f"delete from {SCHEMA_NAME}.tournament_in_release where release_id = {release_id}")


def delete_tournament_result(tournament_id):
    with connection.cursor() as cursor:
        cursor.execute(f"delete from {SCHEMA_NAME}.tournament_result where tournament_id = {tournament_id}")


def build_player_rating_rows(release_id: int, player_rating: PlayerRating) -> List[dict]:
    return [
        {
            "release_id": release_id,
            "player_id": player_id,
            "rating": player["rating"],
            "rating_change": ((player["rating"] - player["prev_rating"]) if player["prev_rating"] else "NULL"),
            "place": player["place"],
        }
        for player_id, player in player_rating.data.iterrows()
        if player["rating"] > 0
    ]


def build_team_rating_rows(release_id: int, teams: pd.DataFrame) -> List[dict]:
    return [
        {
            "release_id": release_id,
            "team_id": team_id,
            "rating": team["rating"],
            "trb": team["trb"],
            "rating_change": ((team["rating"] - team["prev_rating"]) if team["prev_rating"] else "NULL"),
            "place": team["place"] or "NULL",
            "place_change": ((decimal.Decimal(team["place"]) - team["prev_place"]) if team["prev_place"] else "NULL"),
        }
        for team_id, team in teams.iterrows()
    ]


def build_player_rating_by_tournament_rows(release_id: int, player_rating: PlayerRating) -> List[dict]:
    return [
        {
            "release_id": release_id,
            "player_id": player_id,
            "tournament_result_id": rating_by_trnmt.tournament_result_id or "NULL",
            "tournament_id": rating_by_trnmt.tournament_id or "NULL",
            "initial_score": rating_by_trnmt.initial_score,
            "weeks_since_tournament": rating_by_trnmt.weeks_since_tournament,
            "cur_score": rating_by_trnmt.cur_score,
        }
        for player_id, player in player_rating.data.iterrows()
        if player["rating"] != 0
        for rating_by_trnmt in player["top_bonuses"]
    ]


def build_tournaments_in_release_rows(release_id: int, tournaments: Iterable[trnmt.Tournament]) -> List[dict]:
    return [
        {"release_id": release_id, "tournament_id": tournament.id}
        for tournament in tournaments
        if tournament.is_in_maii_rating
    ]


# Builds the already-calculated tournament bonuses rows (without touching the DB).
def build_tournament_result_rows(trnmt: trnmt.Tournament) -> List[dict]:
    return [
        {
            "tournament_id": trnmt.id,
            "team_id": team["team_id"],
            "mp": team["expected_place"],
            "bp": team["score_pred"],
            "m": team["position"],
            "rating": team["score_real"],
            "d1": team["D1"],
            "d2": team["D2"],
            "rating_change": team["bonus"],
            "r": team["r"],
            "rt": team["rt"],
            "rb": team["rb"],
            "rg": team["rg"],
            "is_in_maii_rating": "TRUE" if team["heredity"] else "FALSE",
        }
        for _, team in trnmt.data.iterrows()
    ]


def dump_rating_for_next_release(old_release: models.Release, teams_with_updated_rating: List[Tuple[int, int]]):
    for team_id, new_rating in teams_with_updated_rating:
        n_changed = old_release.team_rating_set.filter(team_id=team_id).update(rating_for_next_release=new_rating)
        if n_changed != 1:
            logger.warning(
                "dump_rating_for_next_release: there is problem with updating team_rating.rating_for_next_release for "
                + f"team_id {team_id}, new rating {new_rating}: {n_changed} rows are affected."
            )


# Loads tournaments from our DB that finish between given releases.
def get_tournaments_for_release(old_release: models.Release, new_release: models.Release) -> List[trnmt.Tournament]:
    tournaments = []
    n_counted_in_maii_rating = 0
    tournaments_qs = models.Tournament.objects.filter(
        end_datetime__date__gt=old_release.date,
        end_datetime__date__lte=new_release.date,
    ).prefetch_related("roster_set", "team_score_set__team")
    if new_release.date <= tools.FIRST_NEW_RELEASE:
        tournaments_qs = tournaments_qs.filter(maii_rating=True)
    for trnmt_from_db in tournaments_qs.order_by("pk"):
        # We need only tournaments with available results of at lease some teams.
        try:
            tournament = trnmt.Tournament(trnmt_from_db=trnmt_from_db, release=new_release)
            tournaments.append(tournament)
            if trnmt_from_db.maii_rating:
                n_counted_in_maii_rating += 1
        except trnmt.EmptyTournamentException as e:
            if trnmt_from_db.maii_rating:
                logger.warning(f"Skipping tournament with id {trnmt_from_db.id}: {e}")

    logger.debug(
        f"There are {len(tournaments)} tournaments ({n_counted_in_maii_rating} in MAII rating) with at least one "
        f"result between {old_release.date} and {new_release.date}."
    )
    return tournaments


# A.2.2: We only calculate rating for teams that have base roster in current season,
# or that had it in previous season and new season started <=3 months ago.
def teams_to_dump(release_date: datetime.date, teams: TeamRating) -> pd.DataFrame:
    cur_season = db_tools.get_season(release_date)
    teams_with_rosters = set(cur_season.season_roster_set.values_list("team_id", flat=True).distinct())
    if cur_season.start + datetime.timedelta(days=90) >= release_date:
        prev_season = db_tools.get_season(release_date - datetime.timedelta(days=180))
        teams_with_rosters |= set(prev_season.season_roster_set.values_list("team_id", flat=True).distinct())
    teams.data[teams.data.index.isin(teams_with_rosters)]
    n_skipped_teams = len(teams.data[~teams.data.index.isin(teams_with_rosters)])
    if n_skipped_teams:
        logger.debug(f"We exclude from the rating {n_skipped_teams} teams that have no roster for current season.")
    return teams.data[teams.data.index.isin(teams_with_rosters)]


# Reads teams and players for provided dates; finds tournaments for next release; calculates
# new ratings and writes them to our DB.
def calc_release(next_release_date: datetime.date):
    old_release_date = tools.get_prev_release_date(next_release_date)
    old_release = models.Release.objects.get(date=old_release_date)
    initial_teams = get_team_rating(old_release.id)
    next_release, _ = models.Release.objects.get_or_create(date=next_release_date)

    logger.info(
        f"Making a step from release {old_release_date} (id {old_release.id}) to release {next_release_date} (id {next_release.id})"
    )
    initial_players = PlayerRating(release=old_release, release_for_squads=next_release)
    initial_teams.update_q(initial_players)
    if pd.isnull(initial_teams.q):
        sys.exit("Q is nan! We cannot continue.")
    initial_teams.calc_trb(initial_players)

    changed_teams = db_tools.get_teams_with_new_players(old_release_date, next_release_date)
    teams_with_updated_rating = initial_teams.update_ratings_for_changed_teams(changed_teams)
    dump_rating_for_next_release(old_release, teams_with_updated_rating)

    tournaments = get_tournaments_for_release(old_release, next_release)
    logger.info(f"Fetched {len(tournaments)} tournaments")
    new_teams, new_players = make_step_for_teams_and_players(
        initial_teams, initial_players, tournaments, new_release=next_release
    )
    logger.info("Made a step for teams and players")
    new_teams.data["place"] = tools.calc_places(new_teams.data["rating"].values)

    # Build every row we would write, then fingerprint it. The fingerprint covers
    # all written columns, so if it matches the stored one nothing changed and we
    # can skip the (expensive) delete+reinsert entirely.
    tournament_result_rows = {tournament.id: build_tournament_result_rows(tournament) for tournament in tournaments}
    table_rows = {
        "tournament_result": [row for rows in tournament_result_rows.values() for row in rows],
        "player_rating": build_player_rating_rows(next_release.id, new_players),
        "team_rating": build_team_rating_rows(next_release.id, teams_to_dump(next_release_date, new_teams)),
        "player_rating_by_tournament": build_player_rating_by_tournament_rows(next_release.id, new_players),
        "tournament_in_release": build_tournaments_in_release_rows(next_release.id, tournaments),
    }
    release_hash = fingerprint(table_rows)
    if release_hash == next_release.hash:
        logger.info(f"Release {next_release.id} unchanged; skipping write")
        return len(tournaments)

    logger.info("hashes are different, updating release")
    with transaction.atomic():
        for tournament in tournaments:
            delete_tournament_result(tournament.id)
            db_tools.fast_insert("tournament_result", tournament_result_rows[tournament.id])
        logger.info("Saved tournament bonuses")
        delete_previous_results(next_release.id)
        logger.info("Deleted previous results")
        db_tools.fast_insert("player_rating", table_rows["player_rating"])
        db_tools.fast_insert("team_rating", table_rows["team_rating"])
        db_tools.fast_insert("player_rating_by_tournament", table_rows["player_rating_by_tournament"])
        db_tools.fast_insert("tournament_in_release", table_rows["tournament_in_release"])
        logger.info(f"Saved release {next_release.id}")

    next_release.updated_at = timezone.now()
    next_release.hash = release_hash
    next_release.q = new_teams.q
    next_release.save()

    return len(tournaments)


# Calculates all releases starting from FIRST_NEW_RELEASE until current date
def calc_all_releases(first_to_calc: datetime.date, last_to_calc: datetime.date = datetime.date.today()):
    next_release_date = first_to_calc
    time_started = datetime.datetime.now()
    n_releases_calculated = 0
    n_tournaments_total = 0
    last_day_to_calc = last_to_calc + datetime.timedelta(days=7)
    while next_release_date <= last_day_to_calc:
        release_started = datetime.datetime.now()
        n_tournaments = calc_release(next_release_date=next_release_date)
        release_time = datetime.datetime.now() - release_started
        logger.info(f"Release {next_release_date} done in {release_time}, included {n_tournaments} tournaments")
        n_releases_calculated += 1
        n_tournaments_total += n_tournaments
        next_release_date += datetime.timedelta(days=7)
    time_spent = datetime.datetime.now() - time_started
    logger.info(f"Done! Releases calculated: {n_releases_calculated}, tournaments included: {n_tournaments_total}")
    logger.info(
        f"Total time spent: {time_spent}, time per release: {time_spent / n_releases_calculated}, "
        f"time per tournament: {time_spent / n_tournaments_total if n_tournaments_total else 'n/a'}"
    )
