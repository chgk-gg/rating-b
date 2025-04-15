import pandas as pd
from typing import List
import logging

from .tools import calc_tech_rating, get_age_in_weeks
from .constants import N_BEST_TOURNAMENTS_FOR_PLAYER_RATING
from scripts import db_tools, tools
from b import models

logger = logging.getLogger(__name__)


class PlayerRating:
    def __init__(self, release=None, release_for_squads=None, file_path=None):
        if release is None:
            raise Exception("no release is passed")
        if release_for_squads is None:
            raise Exception("no release for squads is passed")

        if file_path:
            self.data = pd.DataFrame.from_csv(file_path, index_col=0)
            return

        self.release = release
        self.release_for_squads = release_for_squads
        self.players_dict = {
            player_rating["player_id"]: player_rating | {"top_bonuses": []}
            for player_rating in self.release.player_rating_set.values(
                "player_id", "rating"
            )
        }

        if self.release.date == tools.LAST_OLD_RELEASE:
            self.load_last_old_release()
        else:
            for player_bonus in self.release.player_rating_by_tournament_set.all():
                self.players_dict[player_bonus.player_id]["top_bonuses"].append(
                    player_bonus
                )
        # adding base_team_ids
        self.data = (
            pd.DataFrame(self.players_dict.values())
            .set_index("player_id")
            .join(
                db_tools.get_base_teams_for_players(self.release_for_squads.date),
                how="left",
            )
        )

    def update_places(self):
        self.data["place"] = (
            self.data["rating"].rank(ascending=False, method="min").astype("Int32")
        )

    def load_last_old_release(self):
        tournament_end_dates = db_tools.get_tournament_end_dates()
        age_in_weeks_by_tournament_id = {}
        for item in models.Player_rating_by_tournament_old.objects.values(
            "player_id", "tournament_id", "rating_original", "rating_now"
        ):
            if item["player_id"] in self.players_dict:
                if item["tournament_id"] not in age_in_weeks_by_tournament_id:
                    age_in_weeks_by_tournament_id[item["tournament_id"]] = (
                        get_age_in_weeks(
                            tournament_end_dates[item["tournament_id"]],
                            self.release_for_squads.date,
                        )
                    )
                bonus = models.Player_rating_by_tournament(
                    release_id=self.release.id,
                    player_id=item["player_id"],
                    weeks_since_tournament=age_in_weeks_by_tournament_id[
                        item["tournament_id"]
                    ],
                    tournament_id=item["tournament_id"],
                    initial_score=item["rating_original"],
                    cur_score=item["rating_now"],
                )
                self.players_dict[item["player_id"]]["top_bonuses"].append(bonus)

    def calc_rt(self, player_ids, q=None):
        """
        вычисляет тех рейтинг по списку id игроков
        """
        prs = self.data.rating.reindex(player_ids).fillna(0).values
        return calc_tech_rating(prs, q)

    def calc_tech_rating_all_teams(self, q=None) -> pd.Series:
        """
        Рассчитывает технический рейтинг по базовому составу для всех команд, у которых есть
        хотя бы один приписанный к ним игрок
        :return: pd.Series, name: rating, index: base_team_id, values: техрейтинги
        """
        res = self.data.groupby("base_team_id")["rating"].apply(
            lambda x: calc_tech_rating(x.values, q)
        )
        res.name = "trb"
        return res

    # Multiplies all existing bonuses by J_i constant
    def reduce_rating(self):
        def reduce_vector(
            player_ratings: List[models.Player_rating_by_tournament],
        ) -> List[models.Player_rating_by_tournament]:
            for player_rating in player_ratings:
                player_rating.recalc_cur_score()
            return player_ratings

        self.data["top_bonuses"] = self.data["top_bonuses"].map(reduce_vector)

    # Removes all bonuses except top 7 and updates rating for each player
    def recalc_rating(self):
        def leave_top_N(
            v: List[models.Player_rating_by_tournament],
        ) -> List[models.Player_rating_by_tournament]:
            return sorted(v, key=lambda x: -x.raw_cur_score)[
                :N_BEST_TOURNAMENTS_FOR_PLAYER_RATING
            ]

        self.data["top_bonuses"] = self.data["top_bonuses"].map(leave_top_N)

        def sum_ratings_now(v: List[models.Player_rating_by_tournament]) -> int:
            return sum(x.cur_score for x in v)

        self.data["rating"] = self.data["top_bonuses"].map(sum_ratings_now)
        self.update_places()
