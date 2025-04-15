import unittest
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from scripts.main import calc_release, calc_all_releases
from b.models import (
    Team_rating,
    Tournament_in_release,
    Player_rating_by_tournament,
    Player_rating,
    Tournament_result,
    Release,
)


class TestReleases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        release_date = date(2021, 9, 16)
        calc_release(release_date)
        calc_all_releases(release_date, release_date + timedelta(days=14))
        cls.release = Release.objects.get(date=release_date)

    def test_team_rating_values(self):
        team_at_first_place = Team_rating.objects.filter(release=self.release).order_by(
            "place"
        )[0]
        self.assertEqual(45556, team_at_first_place.team_id)
        self.assertEqual(10737, team_at_first_place.rating)
        self.assertEqual(63, team_at_first_place.rating_change)
        self.assertEqual(9394, team_at_first_place.trb)
        self.assertEqual(1, team_at_first_place.place)
        self.assertEqual(0, team_at_first_place.place_change)

        team_at_place_57 = Team_rating.objects.filter(release=self.release).order_by(
            "place"
        )[56]
        self.assertEqual(65268, team_at_place_57.team_id)
        self.assertEqual(7652, team_at_place_57.rating)
        self.assertEqual(-83, team_at_place_57.rating_change)
        self.assertEqual(7962, team_at_place_57.trb)
        self.assertEqual(8, team_at_place_57.place_change)
        self.assertEqual(57, team_at_place_57.place)

        team_at_place_400 = Team_rating.objects.filter(release=self.release).order_by(
            "place"
        )[399]
        self.assertEqual(46627, team_at_place_400.team_id)
        self.assertEqual(5288, team_at_place_400.rating)
        self.assertEqual(0, team_at_place_400.rating_change)
        self.assertEqual(0, team_at_place_400.trb)
        self.assertEqual(0, team_at_place_400.place_change)
        self.assertEqual(400, team_at_place_400.place)

    def test_tournaments_in_release_values(self):
        tournaments_in_release = Tournament_in_release.objects.filter(
            release=self.release
        )
        self.assertEqual(
            [6044, 6114, 7225, 7325],
            list(tournaments_in_release.values_list("tournament_id", flat=True)),
        )

    def test_player_rating_values(self):
        player_rating = Player_rating.objects.get(release=self.release, player_id=77673)
        self.assertEqual(12434, player_rating.rating)
        self.assertEqual(33, player_rating.rating_change)
        self.assertEqual(121, player_rating.place)

    def test_missing_player_rating_values(self):
        self.assertEqual(
            0,
            Player_rating.objects.filter(
                release=self.release, player_id=100000
            ).count(),
        )

    def test_player_rating_by_tournament_values(self):
        player_top_bonuses = Player_rating_by_tournament.objects.filter(
            release=self.release, player_id=77673
        )
        self.assertEqual(7, player_top_bonuses.count())

        self.assertEqual(1794, player_top_bonuses.get(tournament_id=7225).cur_score)
        self.assertEqual(1794, player_top_bonuses.get(tournament_id=7225).initial_score)
        self.assertEqual(
            0, player_top_bonuses.get(tournament_id=7225).weeks_since_tournament
        )

        self.assertEqual(1933, player_top_bonuses.get(tournament_id=5923).cur_score)
        self.assertEqual(2053, player_top_bonuses.get(tournament_id=5923).initial_score)
        self.assertEqual(
            6, player_top_bonuses.get(tournament_id=5923).weeks_since_tournament
        )

    def test_tournament_result_values(self):
        tournament_results = Tournament_result.objects.filter(tournament_id=7225)
        self.assertEqual(95, tournament_results.count())

        first_place = tournament_results.order_by("m")[0]
        self.assertEqual(1, first_place.m)
        self.assertEqual(1, first_place.mp)
        self.assertEqual(49804, first_place.team_id)
        self.assertEqual(2079, first_place.rating)
        self.assertEqual(80, first_place.rating_change)
        self.assertEqual(2079, first_place.bp)
        self.assertEqual(0, first_place.d1)
        self.assertEqual(160, first_place.d2)
        self.assertEqual(9568, first_place.rg)
        self.assertEqual(9568, first_place.rt)
        self.assertEqual(0, first_place.r)
        self.assertEqual(False, first_place.is_in_maii_rating)

        # We want to find a specific team around the 20th place instead of fighting ORDER BY randomness
        place_20 = tournament_results.get(team_id=43417)
        self.assertEqual(19.5, place_20.m)
        self.assertEqual(11, place_20.mp)
        self.assertEqual(1380, place_20.rating)
        self.assertEqual(-27, place_20.rating_change)
        self.assertEqual(1532, place_20.bp)
        self.assertEqual(-76, place_20.d1)
        self.assertEqual(22, place_20.d2)
        self.assertEqual(6821, place_20.rg)
        self.assertEqual(7127, place_20.rt)
        self.assertEqual(6954, place_20.r)
        self.assertEqual(True, place_20.is_in_maii_rating)
