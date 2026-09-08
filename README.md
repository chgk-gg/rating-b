# rating-b
## Run locally
Copy `.env.example` to `.env` and update it with your local Postgres details:

```bash
cp .env.example .env
```

`DJANGO_SECRET_KEY` needs to be present but can have any value.

We use [uv](https://docs.astral.sh/uv/) as a package manager. You can [install it with a standalone installer or a package manager like Homebrew](https://docs.astral.sh/uv/getting-started/installation/). To install dependencies, run:

```bash
uv sync
```

## Commands
* `uv run manage.py calc_all_releases [--first_to_calc=2021-09-09]` calculates all releases from first_to_calc until today.
* `uv run manage.py calc_release YYYY-MM-DD` reads previous release data from our DB (it must already exist)
  and creates new release for YYYY-MM-DD (this date must be Thursday for 2021+ and Friday for 2020-).

## Project structure
The top directories are:
* dj -- core Django files.
* b -- Django files specific for rating B model.
  * models.py contains the descriptions of all tables in `b` schema;
  * management/commands/ contains commands that run rating-related computations.
* scripts -- functions that actually read the data from DB, compute ratings, and flush the results to the DB, and tests for them.

## Deployment

rating-b runs on [Fly](https://fly.io/). Deployment is defined in [`fly.toml`](./fly.toml).

Most of the time, we run 0 replicas of this app. Recalculation is triggered from [rating-ui](https://github.com/chgk-gg/rating-ui) in `RatingCalculationJob`. It uses fly.io’s API to start the machine with rating-b and sets `FIRST_RELEASE_DATE` and `LAST_RELEASE_DATE` env variables. It then monitors the machine and destroys it once recalculation is done. 
