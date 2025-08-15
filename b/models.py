from django.db import models

from scripts import constants


### Tables from 'public' scheme. Read-only.


class Town(models.Model):
    title = models.CharField(verbose_name="Название", max_length=100, db_index=True)

    class Meta:
        db_table = "towns"

    def __str__(self):
        return self.name


class Team(models.Model):
    title = models.CharField(verbose_name="Название", max_length=250)
    town = models.ForeignKey(
        Town,
        verbose_name="Город",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        db_table = "teams"


TRNMT_TYPE_UNKNOWN = 1
TRNMT_TYPE_REGULAR = 2
TRNMT_TYPE_SYNCHRONOUS = 3
TRNMT_TYPE_REGIONAL = 4
TRNMT_TYPE_OVERALL = 5
TRNMT_TYPE_STRICT_SYNCHRONOUS = 6
TRNMT_TYPE_ASYNCHRONOUS = 8
TRNMT_TYPE_MARATHON = 10
TRNMT_TYPE_ONLINE = 11
TRNMT_TYPES = {
    TRNMT_TYPE_UNKNOWN: "Неизвестный",
    TRNMT_TYPE_REGULAR: "Обычный",
    TRNMT_TYPE_SYNCHRONOUS: "Синхрон",
    TRNMT_TYPE_REGIONAL: "Региональный",
    TRNMT_TYPE_OVERALL: "Общий зачёт",
    TRNMT_TYPE_STRICT_SYNCHRONOUS: "Строго синхронный",
    TRNMT_TYPE_ASYNCHRONOUS: "Асинхрон",
    TRNMT_TYPE_MARATHON: "Марафон",
    TRNMT_TYPE_ONLINE: "Онлайн",
}


class Tournament(models.Model):
    title = models.CharField(verbose_name="Название", max_length=100)
    typeoft_id = models.SmallIntegerField(verbose_name="Тип турнира", choices=TRNMT_TYPES.items())
    maii_rating = models.BooleanField(verbose_name="Учитывается ли в рейтинге МАИИ")
    start_datetime = models.DateTimeField(verbose_name="Начало отыгрыша")
    end_datetime = models.DateTimeField(verbose_name="Конец отыгрыша")

    class Meta:
        db_table = "tournaments"


class Player(models.Model):
    last_name = models.CharField(verbose_name="Фамилия", max_length=100)
    first_name = models.CharField(verbose_name="Имя", max_length=100)
    patronymic = models.CharField(verbose_name="Отчество", max_length=100)

    class Meta:
        db_table = "players"


class Team_score(models.Model):  # Очки команды на данном турнире
    tournament = models.ForeignKey(Tournament, verbose_name="Турнир", on_delete=models.CASCADE)
    team = models.ForeignKey(Team, verbose_name="Команда", on_delete=models.CASCADE)
    title = models.CharField(
        verbose_name="Название команды на турнире",
        max_length=250,
        db_column="team_title",
    )
    total = models.SmallIntegerField(verbose_name="Число взятых вопросов")
    position = models.DecimalField(verbose_name="Занятое место", default=0, max_digits=5, decimal_places=1)

    class Meta:
        db_table = "tournament_results"
        unique_together = (
            (
                "tournament",
                "team",
            ),
        )


class Roster(models.Model):  # Состав команды на данном турнире
    tournament = models.ForeignKey(Tournament, verbose_name="Турнир", on_delete=models.CASCADE)
    team = models.ForeignKey(Team, verbose_name="Команда", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, verbose_name="Игрок", on_delete=models.CASCADE)
    flag = models.CharField(verbose_name="Флаг (Б или Л)", max_length=1, null=True)
    is_captain = models.BooleanField(verbose_name="Капитан ли команды")

    class Meta:
        db_table = "tournament_rosters"
        unique_together = (
            (
                "tournament",
                "team",
                "player",
            ),
        )


class Season(models.Model):
    start = models.DateField(verbose_name="Начало сезона")
    end = models.DateField(verbose_name="Конец сезона")

    class Meta:
        db_table = "seasons"


class Season_roster(models.Model):  # Базовый состав команды в данном сезоне
    season = models.ForeignKey(Season, verbose_name="Сезон", on_delete=models.PROTECT)
    team = models.ForeignKey(Team, verbose_name="Команда", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, verbose_name="Игрок", on_delete=models.CASCADE)
    start_date = models.DateField(verbose_name="Дата входа в БС", null=True)
    end_date = models.DateField(verbose_name="Дата выхода из БС", null=True)

    class Meta:
        db_table = "base_rosters"
        unique_together = (
            (
                "season",
                "team",
                "player",
            ),
        )


class Player_rating_by_tournament_old(models.Model):
    player = models.ForeignKey(Player, verbose_name="Игрок", on_delete=models.CASCADE, null=True)
    tournament = models.ForeignKey(Tournament, verbose_name="Турнир", on_delete=models.PROTECT, null=True)
    rating_original = models.IntegerField(verbose_name="Бонус игрока за турнир", null=True)
    rating_now = models.IntegerField(verbose_name="Вклад в рейтинг игрока в последнем релизе рейтинга МАК")

    class Meta:
        db_table = "rating_individual_old_details"
        unique_together = (
            (
                "player",
                "tournament",
            ),
        )


### Tables from 'b' scheme. We can write to them.


class Release(models.Model):
    title = models.CharField(verbose_name="Название", max_length=250)
    date = models.DateField(verbose_name="Дата из мира игр", unique=True)
    updated_at = models.DateTimeField(verbose_name="Дата последнего изменения", auto_now=True)
    hash = models.IntegerField(verbose_name="Hash of ratings in this release")
    q = models.DecimalField(max_digits=7, decimal_places=5, verbose_name="Q coefficient for release")

    class Meta:
        db_table = "release"


class Team_rating(models.Model):
    release = models.ForeignKey(Release, verbose_name="Релиз", on_delete=models.CASCADE)
    team = models.ForeignKey(Team, verbose_name="Команда", on_delete=models.PROTECT, null=True)
    # team_id = models.IntegerField(verbose_name='Команда')
    rating = models.IntegerField(verbose_name="Рейтинг команды")
    rating_for_next_release = models.IntegerField(
        verbose_name="Рейтинг команды, использующийся для следующего релиза; непусто, только если рейтинг был пересчитан из-за изменения БС",
        null=True,
        default=None,
    )
    trb = models.IntegerField(verbose_name="Технический рейтинг команды по ее базовому составу TRB")
    rating_change = models.IntegerField(verbose_name="Изменение с прошлого релиза", null=True)
    place = models.DecimalField(verbose_name="Место в релизе", max_digits=7, decimal_places=1, null=True)
    place_change = models.DecimalField(
        verbose_name="Изменение места с прошлого релиза",
        max_digits=7,
        decimal_places=1,
        null=True,
    )

    class Meta:
        db_table = "team_rating"
        unique_together = (
            (
                "release",
                "team",
            ),
        )
        index_together = [
            ["release", "team", "rating"],
            ["release", "team", "rating_change"],
            ["release", "team", "place"],
            ["release", "team", "place_change"],
        ]


# When given team lost heredity to the previous season.
class Team_lost_heredity(models.Model):
    season = models.ForeignKey(Season, verbose_name="Сезон", on_delete=models.PROTECT)
    # season_id = models.IntegerField(verbose_name='Сезон')
    team = models.ForeignKey(Team, verbose_name="Команда", on_delete=models.PROTECT)
    # team_id = models.IntegerField(verbose_name='Команда')
    date = models.DateField(
        verbose_name="Дата релиза, в котором мы пересчитали рейтинг команды; преемственность утрачена на одном из турниров после этого релиза"
    )

    class Meta:
        db_table = "team_lost_heredity"
        unique_together = (
            (
                "season",
                "team",
            ),
        )


class Player_rating(models.Model):
    release = models.ForeignKey(Release, verbose_name="Релиз", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, verbose_name="Игрок", on_delete=models.CASCADE, null=True)
    # player_id = models.IntegerField(verbose_name='Игрок')
    rating = models.IntegerField(verbose_name="Рейтинг игрока")
    rating_change = models.IntegerField(verbose_name="Изменение с прошлого релиза", null=True)
    place = models.DecimalField(verbose_name="Место в релизе", max_digits=7, decimal_places=1, null=True)
    place_change = models.DecimalField(
        verbose_name="Изменение места с прошлого релиза",
        max_digits=7,
        decimal_places=1,
        null=True,
    )

    class Meta:
        db_table = "player_rating"
        unique_together = (
            (
                "release",
                "player",
            ),
        )
        index_together = [
            ["release", "player", "rating"],
            ["release", "player", "rating_change"],
            ["release", "player", "place"],
            ["release", "player", "place_change"],
        ]


class Team_rating_by_player(models.Model):
    team_rating = models.ForeignKey(Team_rating, verbose_name="Рейтинг команды в релизе", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, verbose_name="Игрок", on_delete=models.CASCADE, null=True)
    # player_id = models.IntegerField(verbose_name='Игрок')
    order = models.SmallIntegerField(
        verbose_name="Порядок игрока по рейтингу по убыванию, наибольший рейтинг получает 1"
    )
    contribution = models.IntegerField(verbose_name="Вклад игрока в TRB команды")

    class Meta:
        db_table = "team_rating_by_player"
        unique_together = (
            (
                "team_rating",
                "player",
            ),
        )
        index_together = [
            ["team_rating", "player", "order"],
        ]


class Tournament_result(models.Model):
    tournament = models.ForeignKey(Tournament, verbose_name="Турнир", on_delete=models.PROTECT, null=True)
    # tournament_id = models.IntegerField(verbose_name='Турнир')
    team = models.ForeignKey(Team, verbose_name="Команда", on_delete=models.PROTECT, null=True)
    # team_id = models.IntegerField(verbose_name='Команда')
    mp = models.DecimalField(verbose_name="Предсказанное место", max_digits=6, decimal_places=1)
    bp = models.IntegerField(verbose_name="Предсказанный балл")
    m = models.DecimalField(verbose_name="Занятое место", max_digits=6, decimal_places=1)
    rating = models.IntegerField(verbose_name="Набранный балл B")
    d1 = models.IntegerField(verbose_name="D1")
    d2 = models.IntegerField(verbose_name="D2")
    r = models.IntegerField(verbose_name="R: Релизный рейтинг команды из последнего релиза")
    rt = models.IntegerField(verbose_name="RT: Технический рейтинг команды по фактическому составу")
    rb = models.IntegerField(verbose_name="RB: Технический рейтинг команды по базовому составу")
    rg = models.IntegerField(verbose_name="RG: Используемый рейтинг команды")
    rating_change = models.IntegerField(verbose_name="Результат команды на турнире D")
    is_in_maii_rating = models.BooleanField(verbose_name="Учитывается ли в рейтинге МАИИ")

    class Meta:
        db_table = "tournament_result"
        unique_together = (
            (
                "tournament",
                "team",
            ),
        )
        index_together = [
            ["tournament", "team", "mp"],
            ["tournament", "team", "bp"],
            ["tournament", "team", "m"],
            ["tournament", "team", "rating"],
            ["tournament", "team", "d1"],
            ["tournament", "team", "d2"],
            ["tournament", "team", "rating_change"],
        ]


# We use either tournament_result (for new tournaments) or tournament+initial_score
class Player_rating_by_tournament(models.Model):
    release = models.ForeignKey(Release, verbose_name="Релиз", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, verbose_name="Игрок", on_delete=models.CASCADE, null=True)
    # player_id = models.IntegerField(verbose_name='Игрок')
    tournament_result = models.ForeignKey(
        Tournament_result,
        verbose_name="Результат команды на турнире",
        on_delete=models.CASCADE,
        null=True,
    )
    tournament = models.ForeignKey(Tournament, verbose_name="Турнир", on_delete=models.PROTECT, null=True)
    # tournament_id = models.IntegerField(verbose_name='Турнир', null=True)
    initial_score = models.IntegerField(verbose_name="Бонус игрока за турнир", null=True)
    weeks_since_tournament = models.SmallIntegerField(verbose_name="Число недель, прошедших после турнира, начиная с 0")
    cur_score = models.IntegerField(verbose_name="Вклад в рейтинг игрока в этом релизе")
    raw_cur_score = None  # Float value for better precision

    class Meta:
        db_table = "player_rating_by_tournament"
        unique_together = (
            ("release", "player", "tournament_result"),
            ("release", "player", "tournament"),
        )
        index_together = [
            ["release", "player", "cur_score"],
        ]

    def recalc_cur_score(self):
        self.weeks_since_tournament += 1
        self.raw_cur_score = self.initial_score * (constants.J**self.weeks_since_tournament)
        self.cur_score = round(self.raw_cur_score)


# Stores all tournaments that were counted in given release.
class Tournament_in_release(models.Model):
    release = models.ForeignKey(Release, verbose_name="Релиз", on_delete=models.CASCADE)
    tournament = models.ForeignKey(Tournament, verbose_name="Турнир", on_delete=models.PROTECT)

    # tournament_id = models.IntegerField(verbose_name='Турнир')
    class Meta:
        db_table = "tournament_in_release"
        unique_together = (
            (
                "release",
                "tournament",
            ),
        )
