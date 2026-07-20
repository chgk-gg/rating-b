import datetime
import decimal
import unittest

from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from scripts import db_tools


class TestRoundHalfAway(unittest.TestCase):
    def test_rounds_half_up_for_positive_values(self):
        self.assertEqual(3, db_tools.round_half_away(2.5))
        self.assertEqual(2, db_tools.round_half_away(2.4))

    def test_rounds_half_away_from_zero_for_negative_values(self):
        self.assertEqual(-3, db_tools.round_half_away(-2.5))
        self.assertEqual(-2, db_tools.round_half_away(-2.4))

    def test_matches_postgres_for_floats_not_exactly_representable(self):
        # 0.49999999999999994 + 0.5 == 1.0 in float arithmetic, so a naive
        # floor(x + 0.5) implementation would round this up to 1 instead of 0.
        # Postgres rounds the decimal string it was actually sent, so this must too.
        self.assertEqual(0, db_tools.round_half_away(0.49999999999999994))

    def test_passes_through_integers_unchanged(self):
        self.assertEqual(1234, db_tools.round_half_away(1234))


class TestCanonicalizeRow(unittest.TestCase):
    def test_integer_field_is_rounded_half_away_from_zero(self):
        row = db_tools.canonicalize_row("team_rating", {"rating": 2.5, "trb": -2.5})
        self.assertEqual(3, row["rating"])
        self.assertEqual(-3, row["trb"])

    def test_foreign_key_column_is_resolved_to_target_field_type(self):
        # team_id isn't declared directly on Team_rating; it's the column backing the
        # ForeignKey to Team, so its type must be resolved via field.target_field.
        row = db_tools.canonicalize_row("team_rating", {"team_id": 42.5})
        self.assertEqual(43, row["team_id"])

    def test_decimal_field_is_quantized_to_declared_decimal_places(self):
        row = db_tools.canonicalize_row("team_rating", {"place": 47})
        self.assertEqual(decimal.Decimal("47.0"), row["place"])

    def test_decimal_field_rounds_half_away_from_zero(self):
        row = db_tools.canonicalize_row("team_rating", {"place_change": 1.25})
        self.assertEqual(decimal.Decimal("1.3"), row["place_change"])

    def test_decimal_quantization_unaffected_by_poisoned_global_context(self):
        # scripts.main sets decimal.getcontext().prec = 1 globally (for place_change
        # display rounding). canonicalize_row must use its own context, or quantizing
        # a multi-digit result under that global context would raise InvalidOperation.
        original_prec = decimal.getcontext().prec
        decimal.getcontext().prec = 1
        try:
            row = db_tools.canonicalize_row("team_rating", {"place": 1234.56})
        finally:
            decimal.getcontext().prec = original_prec
        self.assertEqual(decimal.Decimal("1234.6"), row["place"])

    def test_string_values_pass_through_unchanged(self):
        # fast_insert relies on raw SQL fragments like "NULL"/"TRUE" surviving untouched.
        row = db_tools.canonicalize_row("team_rating", {"rating": "NULL", "place": "TRUE"})
        self.assertEqual("NULL", row["rating"])
        self.assertEqual("TRUE", row["place"])

    def test_none_values_pass_through_unchanged(self):
        row = db_tools.canonicalize_row("team_rating", {"rating_change": None})
        self.assertIsNone(row["rating_change"])

    def test_unknown_columns_pass_through_unchanged(self):
        row = db_tools.canonicalize_row("team_rating", {"not_a_real_column": 2.5})
        self.assertEqual(2.5, row["not_a_real_column"])

    def test_non_numeric_fields_pass_through_unchanged(self):
        release_date = datetime.date(2021, 9, 16)
        row = db_tools.canonicalize_row("release", {"date": release_date})
        self.assertEqual(release_date, row["date"])

    def test_big_integer_field_is_rounded(self):
        row = db_tools.canonicalize_row("release", {"hash": 42.5})
        self.assertEqual(43, row["hash"])

    def test_leaves_unrelated_columns_in_the_row_untouched(self):
        row = db_tools.canonicalize_row("team_rating", {"rating": 10.4, "place": 3})
        self.assertEqual(10, row["rating"])
        self.assertEqual(decimal.Decimal("3.0"), row["place"])

    def test_does_not_mutate_input_row(self):
        original = {"rating": 2.5}
        db_tools.canonicalize_row("team_rating", original)
        self.assertEqual(2.5, original["rating"])


if __name__ == "__main__":
    unittest.main()
