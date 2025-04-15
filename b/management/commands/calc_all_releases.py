from django.core.management.base import BaseCommand
import datetime

from scripts import main, tools


class Command(BaseCommand):
    help = "Calculates all releases since September 2021."

    def add_arguments(self, parser):
        parser.add_argument(
            "--first_to_calc", default=tools.FIRST_NEW_RELEASE.strftime("%Y-%m-%d")
        )
        parser.add_argument(
            "--last_to_calc", default=datetime.date.today().strftime("%Y-%m-%d")
        )

    def handle(self, *args, **options):
        first_to_calc = datetime.date(*map(int, options["first_to_calc"].split("-")))
        last_to_calc = datetime.date(*map(int, options["last_to_calc"].split("-")))
        main.calc_all_releases(first_to_calc, last_to_calc)
