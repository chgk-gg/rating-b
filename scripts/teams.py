from .api_util import get_teams_release
from .tools import calc_tech_rating
from .tournament import Tournament
from .players import PlayerRating
import pandas as pd
import numpy as np
from typing import List, Tuple


class TeamRating:
    def __init__(self, api_release_id=None, filename=None, teams_list=None):
        if not (api_release_id or filename or teams_list):
            raise Exception('provide release id, or file with rating, or list of dicts!')
        self.q = 1
        if teams_list:
            self.data = pd.DataFrame(teams_list)
        else:
            if api_release_id:
                raw_rating = get_teams_release(api_release_id)
            else:
                raw_rating = pd.read_csv(filename)
            raw_rating = raw_rating[['Ид', 'Рейтинг', 'ТРК по БС']]
            raw_rating.columns = ['team_id', 'rating', 'trb']
            self.data = raw_rating
        self.data.set_index('team_id', inplace=True)
        self.data['prev_rating'] = 0
        self.c = self.calc_c()

    def update_q(self, players_release):
        """
        Коэффициент Q вычисляется при релизе как среднее значение отношения рейтинга R к техническому
        рейтингу по базовому составу RB для команд, входящих в 100 лучших по последнему релизу
        (исключая те, которые получают в этом релизе стартовые рейтинги) и имеющих не менее шести
        игроков в базовом составе.
        """
        top_h = self.data.iloc[:100]
        top_h_ids = set(top_h.index)
        rb_raws = players_release.data[players_release.data['base_team_id'].isin(top_h_ids)].groupby(
            'base_team_id')['rating'].apply(
            lambda x: calc_tech_rating(x.values) if len(x.values) >= 6 else None).dropna()
        top_h = top_h.join(rb_raws, rsuffix='_raw', how='inner')
        self.q = (top_h['rating'] / top_h['rating_raw']).mean()

    def calc_c(self):
        ratings = np.copy(self.data.rating.values)
        ratings[::-1].sort()
        return 2300 / ratings[:15].dot(2. ** np.arange(0, -15, -1))

    def get_team_rating(self, team_id):
        return self.data.rating.get(team_id, 0)

    def get_trb(self, team_id):
        return self.data.trb.get(team_id, 0)

    # Returns tuples of team IDs with changed rating along with new rating
    # TODO: add a separate test for this!
    def update_ratings_for_changed_teams(self, changed_teams) -> List[Tuple[int, int]]:
        existing_teams = [t for t in changed_teams if t in set(self.data.index)]
        self.data['old_release_rating'] = self.data['rating']
        self.data.loc[existing_teams, 'rating'] = np.maximum(
            self.data.loc[existing_teams, 'rating'], self.data.loc[existing_teams, "trb"] * 0.8)
        res = []
        for team_id, team in self.data[self.data['old_release_rating'] != self.data['rating']].iterrows():
            res.append((team_id, team['rating']))
        self.data.drop(columns=['old_release_rating'], inplace=True)
        return res

    def add_new_teams(self, tournament: Tournament, player_rating: PlayerRating):
        new_teams = tournament.data.loc[~tournament.data.team_id.isin(set(self.data.index)),
                                    ['team_id', 'baseTeamMembers']].set_index("team_id")
        if len(new_teams.index) == 0: # Otherwise some strange things happen in the next lines.
            return
        new_teams['trb'] = new_teams.baseTeamMembers.map(lambda x: player_rating.calc_rt(x, self.q))
        new_teams['trb'].fillna(0, inplace=True)
        new_teams['rating'] = new_teams['trb'] * 0.8
        self.data = self.data.append(new_teams.drop("baseTeamMembers", axis=1))

    def calc_trb(self, player_rating: PlayerRating):
        self.data['trb'] = player_rating.calc_tech_rating_all_teams(q=self.q)
        self.data['trb'].fillna(0, inplace=True)
