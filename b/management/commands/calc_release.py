from django.core.management.base import BaseCommand
import datetime

from scripts import main


class Command(BaseCommand):
    help = "Calculates one release based on the previous ones."

    def add_arguments(self, parser):
        parser.add_argument("new_release_date")

    def handle(self, *args, **options):
        new_release_date = datetime.date(*map(int, options["new_release_date"].split("-")))
        main.calc_release(new_release_date)
