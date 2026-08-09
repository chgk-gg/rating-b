import datetime
import unittest

from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from django.db import transaction

from b import models
from scripts import db_tools

PREV_SEASON_ID = 990_098
SEASON_ID = 990_099
PREV_SEASON_START = datetime.date(2098, 8, 29)
SEASON_START = datetime.date(2099, 8, 28)
SEASON_END = datetime.date(2100, 8, 26)

OLD_RELEASE = datetime.date(2099, 10, 1)
NEW_RELEASE = datetime.date(2099, 10, 8)
LAST_RELEASE_OF_PREV_SEASON = datetime.date(2099, 8, 27)
FIRST_RELEASE_OF_SEASON = datetime.date(2099, 9, 3)

TEAM_ID = 990_001
OTHER_TEAM_ID = 990_002


class TestGetTeamsWithNewPlayers(unittest.TestCase):
    """
    Everything here is created inside a transaction that is rolled back afterwards.
    """

    def setUp(self):
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.addCleanup(self.rollback)
        self.prev_season = models.Season.objects.create(
            id=PREV_SEASON_ID, start=PREV_SEASON_START, end=SEASON_START - datetime.timedelta(days=1)
        )
        self.season = models.Season.objects.create(id=SEASON_ID, start=SEASON_START, end=SEASON_END)
        self.next_player_id = 990_001

    def rollback(self):
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def add_to_roster(self, start_date, team_id=TEAM_ID, season=None):
        self.next_player_id += 1
        return models.Season_roster.objects.create(
            season=season or self.season,
            team_id=team_id,
            player_id=self.next_player_id,
            start_date=start_date,
        )

    def test_player_added_between_the_releases(self):
        self.add_to_roster(datetime.date(2099, 10, 5))
        self.assertEqual([TEAM_ID], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_player_added_before_the_previous_release(self):
        self.add_to_roster(datetime.date(2099, 9, 24))
        self.assertEqual([], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_player_added_after_the_new_release(self):
        self.add_to_roster(datetime.date(2099, 10, 15))
        self.assertEqual([], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_start_date_on_the_new_release_counts(self):
        self.add_to_roster(NEW_RELEASE)
        self.assertEqual([TEAM_ID], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_start_date_on_the_old_release_does_not_count(self):
        self.add_to_roster(OLD_RELEASE)
        self.assertEqual([], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_roster_for_the_next_season_filled_in_advance(self):
        # Teams may fill in the base roster before the season starts.
        # That future roster should not be fetched for the current season.
        self.add_to_roster(datetime.date(2099, 8, 10))
        self.assertEqual(
            [],
            db_tools.get_teams_with_new_players(datetime.date(2099, 8, 6), datetime.date(2099, 8, 13)),
        )

    def test_roster_filled_in_advance_counts_from_the_start_of_its_season(self):
        self.add_to_roster(datetime.date(2099, 8, 10))
        self.assertEqual(
            [TEAM_ID],
            db_tools.get_teams_with_new_players(LAST_RELEASE_OF_PREV_SEASON, FIRST_RELEASE_OF_SEASON),
        )

    def test_roster_without_start_date_counts_from_the_start_of_its_season(self):
        self.add_to_roster(None)
        self.assertEqual(
            [TEAM_ID],
            db_tools.get_teams_with_new_players(LAST_RELEASE_OF_PREV_SEASON, FIRST_RELEASE_OF_SEASON),
        )
        self.assertEqual([], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_other_seasons_are_ignored(self):
        self.add_to_roster(datetime.date(2099, 10, 5), season=self.prev_season)
        self.assertEqual([], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_several_new_players_in_one_team(self):
        self.add_to_roster(datetime.date(2099, 10, 5))
        self.add_to_roster(datetime.date(2099, 10, 6))
        self.assertEqual([TEAM_ID], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))

    def test_several_changed_teams(self):
        self.add_to_roster(datetime.date(2099, 10, 5))
        self.add_to_roster(datetime.date(2099, 10, 6), team_id=OTHER_TEAM_ID)
        self.assertEqual(
            [TEAM_ID, OTHER_TEAM_ID],
            sorted(db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE)),
        )

    def test_no_rosters_changed(self):
        self.assertEqual([], db_tools.get_teams_with_new_players(OLD_RELEASE, NEW_RELEASE))


if __name__ == "__main__":
    unittest.main()
