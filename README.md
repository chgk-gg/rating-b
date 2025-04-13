# rating-b
## Run locally
Copy `.env.example` to `.env` and update it with your local Postgres details:

```bash
cp .env.example .env
```

`DJANGO_SECRET_KEY` needs to be present but can have any value.

Create a virtual environment, install dependencies:

```bash
python -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt
```

## Commands
* `python manage.py calc_all_releases [--first_to_calc=2021-09-09]` calculates all releases from first_to_calc until today.
* `python manage.py calc_release YYYY-MM-DD` reads previous release data from our DB (it must already exist)
  and creates new release for YYYY-MM-DD (this date must be Thursday for 2021+ and Friday for 2020-).

## Project structure
The top directories are:
* dj -- core Django files.
* b -- Django files specific for rating B model.
  * models.py contains the descriptions of all tables in `b` schema;
  * management/commands/ contains commands that run rating-related computations.
* scripts -- functions that actually read the data from DB, compute ratings, and flush the results to the DB, and tests for them.

## Deployment
rating-b runs on [Fly](https://fly.io/). Deployment is defined in [`fly.toml`](./fly.toml) and has one process: `supercronic /app/crontab`.

[Supercronic](https://github.com/aptible/supercronic) is [recommended by Fly for cron jobs](https://fly.io/docs/app-guides/supercronic/): it loads environment variables, forwards job logs to stdout and stderr, and handles sigterm signals. We install it in the final section of [`Dockerfile`](./Dockerfile).

Cron jobs are set up in [`crontab`](./crontab). For now, we recalculate all releases every three hours: this job takes about 30 minutes (as of April 2023), so there’s not much sense in making things more complicated.
