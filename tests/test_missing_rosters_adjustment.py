import unittest

from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from scripts.tournament import Tournament


class TestMissingRostersAdjustment(unittest.TestCase):
    def setUp(self):
        self.teams = {
            1: {"position": 1},
            2: {"position": 2},
            3: {"position": 3},
        }

        self.more_teams = {
            1: {"position": 1},
            2: {"position": 2},
            3: {"position": 3.5},
            4: {"position": 3.5},
            5: {"position": 5},
            6: {"position": 6},
        }

    def test_no_missing_rosters_(self):
        teams = Tournament.adjust_for_missing_rosters([], self.teams)
        self.assertEqual(teams, self.teams)

    def test_missing_roster_middle(self):
        teams = Tournament.adjust_for_missing_rosters([2], self.teams)
        expected = {
            1: {"position": 1},
            3: {"position": 2},
        }
        self.assertEqual(expected, teams)

    def test_missing_roster_last_place(self):
        teams = Tournament.adjust_for_missing_rosters([3], self.teams)
        expected = {
            1: {"position": 1},
            2: {"position": 2},
        }
        self.assertEqual(expected, teams)

    def test_missing_roster_first_place(self):
        teams = Tournament.adjust_for_missing_rosters([1], self.teams)
        expected = {
            2: {"position": 1},
            3: {"position": 2},
        }
        self.assertEqual(expected, teams)

    def test_multiple_missing_rosters(self):
        updated_teams = Tournament.adjust_for_missing_rosters([2, 5], self.more_teams)
        expected = {
            1: {"position": 1},
            3: {"position": 2.5},
            4: {"position": 2.5},
            6: {"position": 4},
        }
        self.assertEqual(expected, updated_teams)

    def test_missing_roster_shared_position(self):
        updated_teams = Tournament.adjust_for_missing_rosters([4], self.more_teams)
        expected = {
            1: {"position": 1},
            2: {"position": 2},
            3: {"position": 3},
            5: {"position": 4},
            6: {"position": 5},
        }
        self.assertEqual(expected, updated_teams)
