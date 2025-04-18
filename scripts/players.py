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
        self.data = pd.DataFrame()
        if file_path:
            self.data = pd.DataFrame.from_csv(file_path, index_col=0)
            return
        if release is None:
            raise Exception("no release is passed")
        if release_for_squads is None:
            raise Exception("no release for squads is passed")
        players_dict = {
            player_rating["player_id"]: player_rating | {"top_bonuses": []}
            for player_rating in release.player_rating_set.values("player_id", "rating")
        }

        if release.date == tools.LAST_OLD_RELEASE:
            # In this case we have to load individual bonuses from the special table.
            tournament_end_dates = db_tools.get_tournament_end_dates()
            age_in_weeks_by_tournament_id = {}
            for item in models.Player_rating_by_tournament_old.objects.values(
                "player_id", "tournament_id", "rating_original", "rating_now"
            ):
                if item["player_id"] in players_dict:
                    if item["tournament_id"] not in age_in_weeks_by_tournament_id:
                        age_in_weeks_by_tournament_id[item["tournament_id"]] = (
                            get_age_in_weeks(
                                tournament_end_dates[item["tournament_id"]],
                                release_for_squads.date,
                            )
                        )
                    bonus = models.Player_rating_by_tournament(
                        release_id=release.id,
                        player_id=item["player_id"],
                        weeks_since_tournament=age_in_weeks_by_tournament_id[
                            item["tournament_id"]
                        ],
                        tournament_id=item["tournament_id"],
                        initial_score=item["rating_original"],
                        cur_score=item["rating_now"],
                    )
                    players_dict[item["player_id"]]["top_bonuses"].append(bonus)
        else:
            for player_bonus in release.player_rating_by_tournament_set.all():
                players_dict[player_bonus.player_id]["top_bonuses"].append(player_bonus)
        # adding base_team_ids
        self.data = (
            pd.DataFrame(players_dict.values())
            .set_index("player_id")
            .join(
                db_tools.get_base_teams_for_players(release_for_squads.date), how="left"
            )
        )

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

    # For debug purposes
    def print_top_bonuses(self, player_id: int):
        for item in self.data.loc[player_id]["top_bonuses"]:
            logger.debug(
                f"{item.tournament_id} {item.initial_score} {item.weeks_since_tournament} {item.cur_score}"
            )
