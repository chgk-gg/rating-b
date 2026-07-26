import unittest
from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from scripts.teams import TeamRating
from scripts.constants import NEW_TEAMS_LOWERING_COEFFICIENT, TEAMS_COUNT_FOR_BP


# TeamRating needs at least TEAMS_COUNT_FOR_BP teams to calculate C, so we pad the teams
# we actually care about with filler ones. Fillers have zero trb, so their rating never changes.
def make_team_rating(teams):
    fillers = [
        {"team_id": 1000 + i, "rating": 100 - i, "trb": 0, "place": len(teams) + i + 1}
        for i in range(TEAMS_COUNT_FOR_BP)
    ]
    return TeamRating(teams_list=teams + fillers)


class TestUpdateRatingsForChangedTeams(unittest.TestCase):
    def setUp(self):
        # 1: trb * 0.8 = 4000 < 5000, so the rating stays as it is;
        # 2: trb * 0.8 = 4000 > 3000, so the rating grows to 4000;
        # 3: trb * 0.8 = 2000 == 2000, so the rating stays as it is;
        # 4: trb * 0.8 = 1600 > 1000, so the rating grows to 1600.
        self.teams = make_team_rating(
            [
                {"team_id": 1, "rating": 5000, "trb": 5000, "place": 1},
                {"team_id": 2, "rating": 3000, "trb": 5000, "place": 2},
                {"team_id": 3, "rating": 2000, "trb": 2500, "place": 3},
                {"team_id": 4, "rating": 1000, "trb": 2000, "place": 4},
            ]
        )

    def test_rating_grows_to_lowered_trb(self):
        updated = self.teams.update_ratings_for_changed_teams([2])
        self.assertEqual([(2, 5000 * NEW_TEAMS_LOWERING_COEFFICIENT)], updated)
        self.assertEqual(4000, self.teams.get_team_rating(2))

    def test_rating_never_decreases(self):
        updated = self.teams.update_ratings_for_changed_teams([1])
        self.assertEqual([], updated)
        self.assertEqual(5000, self.teams.get_team_rating(1))

    def test_equal_rating_is_not_reported_as_changed(self):
        updated = self.teams.update_ratings_for_changed_teams([3])
        self.assertEqual([], updated)
        self.assertEqual(2000, self.teams.get_team_rating(3))

    def test_several_changed_teams(self):
        updated = self.teams.update_ratings_for_changed_teams([1, 2, 3, 4])
        self.assertEqual([(2, 4000), (4, 1600)], sorted(updated))
        self.assertEqual(4000, self.teams.get_team_rating(2))
        self.assertEqual(1600, self.teams.get_team_rating(4))

    def test_teams_outside_the_list_are_not_touched(self):
        self.teams.update_ratings_for_changed_teams([2])
        self.assertEqual(5000, self.teams.get_team_rating(1))
        self.assertEqual(2000, self.teams.get_team_rating(3))
        self.assertEqual(1000, self.teams.get_team_rating(4))

    def test_unknown_teams_are_ignored(self):
        updated = self.teams.update_ratings_for_changed_teams([2, 100500])
        self.assertEqual([(2, 4000)], updated)
        self.assertEqual(0, self.teams.get_team_rating(100500))

    def test_no_changed_teams(self):
        updated = self.teams.update_ratings_for_changed_teams([])
        self.assertEqual([], updated)
        self.assertEqual([5000, 3000, 2000, 1000], [self.teams.get_team_rating(i) for i in (1, 2, 3, 4)])

    def test_helper_column_is_dropped(self):
        self.teams.update_ratings_for_changed_teams([2])
        self.assertNotIn("old_release_rating", self.teams.data.columns)

    def test_other_columns_are_kept(self):
        self.teams.update_ratings_for_changed_teams([2])
        self.assertEqual(5000, self.teams.get_trb(2))
        self.assertEqual(2, self.teams.data.place.get(2))
        self.assertEqual(2, self.teams.data.prev_place.get(2))

    def test_team_with_zero_trb(self):
        teams = make_team_rating(
            [
                {"team_id": 1, "rating": 5000, "trb": 5000, "place": 1},
                {"team_id": 2, "rating": 0, "trb": 0, "place": 2},
            ]
        )
        updated = teams.update_ratings_for_changed_teams([1, 2])
        self.assertEqual([], updated)
        self.assertEqual(0, teams.get_team_rating(2))
