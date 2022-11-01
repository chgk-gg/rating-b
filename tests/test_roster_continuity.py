import unittest
from scripts.roster_continuity import *


class TestRosterContinuity(unittest.TestCase):
    def test_rule_selection_before_maii(self):
        old_rule = select_rule(datetime.date(2019, 1, 1))
        self.assertIsInstance(old_rule, Pre2021Rule)

    def test_rule_selection_first_maii_rule(self):
        late_2021_rule = select_rule(datetime.date(2021, 12, 1))
        self.assertIsInstance(late_2021_rule, MAIIRule2021to2022)

    def test_rule_selection_second_maii_rule(self):
        late_2022_rule = select_rule(datetime.date(2022, 12, 1))
        self.assertIsInstance(late_2022_rule, MAIIRuleFrom2022)

    def test_old_rule_more_than_four_base_players(self):
        self.assertTrue(Pre2021Rule().counts(6, 0))
        self.assertTrue(Pre2021Rule().counts(6, 1))
        self.assertTrue(Pre2021Rule().counts(6, 2))
        self.assertTrue(Pre2021Rule().counts(6, 3))
        self.assertTrue(Pre2021Rule().counts(5, 0))
        self.assertTrue(Pre2021Rule().counts(5, 1))
        self.assertTrue(Pre2021Rule().counts(5, 2))
        self.assertTrue(Pre2021Rule().counts(5, 3))
        self.assertTrue(Pre2021Rule().counts(4, 0))
        self.assertTrue(Pre2021Rule().counts(4, 1))
        self.assertTrue(Pre2021Rule().counts(4, 2))
        self.assertTrue(Pre2021Rule().counts(4, 3))
        self.assertTrue(Pre2021Rule().counts(4, 4))

    def test_old_rule_three_players_different_name(self):
        self.assertFalse(Pre2021Rule().counts(3, 0, False))
        self.assertFalse(Pre2021Rule().counts(3, 1, False))
        self.assertFalse(Pre2021Rule().counts(3, 2, False))
        self.assertFalse(Pre2021Rule().counts(3, 3, False))

    def test_old_rule_three_players_base_name(self):
        self.assertTrue(Pre2021Rule().counts(3, 0, True))
        self.assertTrue(Pre2021Rule().counts(3, 1, True))
        self.assertTrue(Pre2021Rule().counts(3, 2, True))
        self.assertTrue(Pre2021Rule().counts(3, 3, True))

    def test_old_rule_not_enough_players(self):
        self.assertFalse(Pre2021Rule().counts(0, 1))
        self.assertFalse(Pre2021Rule().counts(0, 2))
        self.assertFalse(Pre2021Rule().counts(0, 3))
        self.assertFalse(Pre2021Rule().counts(0, 4))
        self.assertFalse(Pre2021Rule().counts(0, 5))
        self.assertFalse(Pre2021Rule().counts(0, 6))
        self.assertFalse(Pre2021Rule().counts(1, 0))
        self.assertFalse(Pre2021Rule().counts(1, 1))
        self.assertFalse(Pre2021Rule().counts(1, 2))
        self.assertFalse(Pre2021Rule().counts(1, 3))
        self.assertFalse(Pre2021Rule().counts(1, 4))
        self.assertFalse(Pre2021Rule().counts(1, 5))
        self.assertFalse(Pre2021Rule().counts(1, 6))
        self.assertFalse(Pre2021Rule().counts(2, 0))
        self.assertFalse(Pre2021Rule().counts(2, 1))
        self.assertFalse(Pre2021Rule().counts(2, 2))
        self.assertFalse(Pre2021Rule().counts(2, 3))
        self.assertFalse(Pre2021Rule().counts(2, 4))
        self.assertFalse(Pre2021Rule().counts(2, 5))


if __name__ == '__main__':
    unittest.main()
