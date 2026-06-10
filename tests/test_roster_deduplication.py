import unittest
from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from scripts.tournament import RosterEntry, Tournament


class TestRosterDeduplication(unittest.TestCase):
    def test_single_team_unchanged(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(10, 1, "Б"), RosterEntry(20, 2, "Л")]
        )
        self.assertEqual({1: 10, 2: 20}, chosen)

    def test_base_team_kept(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(10, 1, "Б"), RosterEntry(20, 1, "Л")]
        )
        self.assertEqual({1: 10}, chosen)

    def test_base_team_kept_regardless_of_order(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(20, 1, "Л"), RosterEntry(10, 1, "Б")]
        )
        self.assertEqual({1: 10}, chosen)

    def test_base_team_kept_when_base_has_larger_id(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(10, 1, "Л"), RosterEntry(20, 1, "Б")]
        )
        self.assertEqual({1: 20}, chosen)

    def test_two_base_teams_smallest_id(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(20, 1, "Б"), RosterEntry(10, 1, "Б")]
        )
        self.assertEqual({1: 10}, chosen)

    def test_two_legionnaire_teams_smallest_id(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(20, 1, "Л"), RosterEntry(10, 1, "Л")]
        )
        self.assertEqual({1: 10}, chosen)

    def test_null_flags_smallest_id(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(20, 1, None), RosterEntry(10, 1, None)]
        )
        self.assertEqual({1: 10}, chosen)

    def test_three_teams_one_base(self):
        chosen = Tournament.deduplicate_rosters(
            [RosterEntry(10, 1, "Л"), RosterEntry(30, 1, "Б"), RosterEntry(20, 1, "Л")]
        )
        self.assertEqual({1: 30}, chosen)

    def test_mix_of_duplicated_and_unique_players(self):
        chosen = Tournament.deduplicate_rosters(
            [
                RosterEntry(10, 1, "Б"),
                RosterEntry(20, 1, "Л"),
                RosterEntry(20, 2, "Б"),
                RosterEntry(30, 3, "Л"),
                RosterEntry(40, 3, "Л"),
            ]
        )
        self.assertEqual({1: 10, 2: 20, 3: 30}, chosen)


if __name__ == "__main__":
    unittest.main()
