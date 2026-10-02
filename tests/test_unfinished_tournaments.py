import datetime
import unittest
from unittest import mock

from dotenv import load_dotenv

load_dotenv("../.env.test")

import django

django.setup()

from b import models
from scripts import main


class TestUnfinishedTournaments(unittest.TestCase):
    """
    Tournaments between releases 2021-09-09 and 2021-09-16 are 6044, 6114, 7225 and 7325;
    7325 is the last one of them to end.
    """

    def setUp(self):
        self.old_release = models.Release.objects.get(date=datetime.date(2021, 9, 9))
        self.new_release = models.Release(date=datetime.date(2021, 9, 16))
        # end_datetime is stored without time zone and read back as naive; the DB session interprets it as UTC.
        self.last_end = models.Tournament.objects.get(pk=7325).end_datetime.replace(tzinfo=datetime.UTC)

    def maii_tournament_ids(self, now: datetime.datetime) -> list[int]:
        with mock.patch.object(main.timezone, "now", return_value=now):
            tournaments = main.get_tournaments_for_release(self.old_release, self.new_release)
        return [tournament.id for tournament in tournaments if tournament.is_in_maii_rating]

    def test_all_tournaments_finished(self):
        now = datetime.datetime(2021, 9, 16, tzinfo=datetime.UTC)
        self.assertEqual([6044, 6114, 7225, 7325], self.maii_tournament_ids(now))

    def test_unfinished_tournament_is_skipped(self):
        now = self.last_end - datetime.timedelta(minutes=30)
        self.assertEqual([6044, 6114, 7225], self.maii_tournament_ids(now))

    def test_tournament_ending_exactly_now_is_included(self):
        now = self.last_end
        self.assertEqual([6044, 6114, 7225, 7325], self.maii_tournament_ids(now))
