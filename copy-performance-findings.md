# COPY vs INSERT: performance findings

Investigation into why switching the large-table writes from multi-row `INSERT`
to `COPY` (commit `0a35dbe`) only moved a full release calc from ~80s to
~50–60s instead of something more dramatic.

## Setup

- Run against a backup of the production DB in Docker (`postgres:17`, `localhost:5432`).
- Profiled a single `calc_release` for **2026-06-11** (release id 442).
- Hot tables for that release:
  - `player_rating_by_tournament` — **300,784 rows**
  - `player_rating` — **73,021 rows**
  - `team_rating` — 3,038 rows
  - `tournament_in_release` — 11 rows

## Headline conclusion

`COPY` only removes the *statement parsing / multi-row `VALUES` building /
network round-trip* overhead. That was a **minority** of the cost. The two
things that actually dominate a release calc are untouched by the write method:

1. **`copy.deepcopy` of the pandas DataFrames** in the pure-Python calc phase.
2. **Dead-tuple unique-index visibility checks** during the write, caused by the
   `DELETE … where release_id = X` + reinsert-same-keys pattern inside one
   transaction. This per-row server-side cost is **identical for `COPY` and
   `INSERT`**.

That is why the gain was modest.

## Experiment 1 — full `calc_release` breakdown (42.6s total)

cProfile + per-table timing of one release calc:

| Phase | Time | Notes |
|---|---|---|
| `make_step_for_teams_and_players` | **18.8s** | of which **`copy.deepcopy` = 18.2s** (11M `deepcopy` calls deep-copying the team/player DataFrames element by element, `scripts/main.py:59-60`) |
| `save_player_rating_by_tournament` (300k rows) | **12.5s** | build CSV 2.3s + `copy_expert` 10.2s (table was bloated, see Exp. 2/3) |
| `PlayerRating.__init__` (reads initial data) | 4.4s | DB read, not a write |
| `save_player_rating` (73k rows) | 4.2s | build CSV 3.7s + `copy_expert` 0.5s |
| `save_team_ratings` (3k rows) | 0.27s | |
| commit (deferred FK check) + misc | ~2s | variable |

The deepcopy and the `player_rating_by_tournament` write together are ~30s of
the 42.6s. Neither is helped by `COPY`.

> Note: release 442 happened to have **0 tournaments**, so `tournament_result`
> writes were not exercised in this profile. A release with tournaments adds
> `dump_team_bonuses_for_tournament` cost on top, with the same DELETE+reinsert
> characteristics.

## Experiment 2 — where the write cost actually is

Isolated `COPY` of the same 300,784 `player_rating_by_tournament` rows under
different conditions:

| Scenario | Time |
|---|---|
| `COPY` into empty heap table, **no indexes** | **0.13s** |
| `COPY` into empty table **with its 3 indexes** | **1.2s** |
| Server-side `COPY FROM '/tmp/file'` (with indexes) | 1.18s |
| `copy_expert` from a Python `StringIO` into empty indexed table | 1.2s |
| `COPY` after `DELETE` of the same keys, **same transaction** (current code, bloated table) | **6.1s** |
| Old multi-row `INSERT` (batch 5000) after the same `DELETE`, same transaction | **5.8s** |

Reads:

- **Index maintenance** alone takes the write from 0.13s → 1.2s (~9×). The table
  has three indexes (see below).
- **`copy_expert` streaming from Python is not the bottleneck** — into an empty
  indexed table it matches a server-side `COPY FROM` file (~1.2s). Raising the
  read buffer (`size=1<<20`) made no difference.
- **The DELETE+reinsert-in-one-transaction pattern is the bottleneck**: 6.1s,
  ~5× slower than loading into an empty indexed table.
- **`COPY` (6.1s) ≈ old `INSERT` (5.8s)** in that pattern. The cost is
  server-side and method-independent, which is the core reason `COPY` didn't
  help here.

### Why DELETE+reinsert in one transaction is slow

The unique index `(release_id, player_id, tournament_id)` still contains the
entries for the just-deleted rows (they're dead but uncommitted, so not
vacuumable yet). Every newly inserted row whose key matches a deleted one must do
a uniqueness check that walks those dead index entries and performs heap
visibility lookups. With a full key overlap (every release_id key is deleted then
re-inserted), this happens for all 300k rows.

## Experiment 3 — DELETE mitigations (none give a clean win)

Tested on a less-bloated table state (hence lower baseline numbers — the penalty
scales with bloat, see below):

| Approach | Result |
|---|---|
| `DELETE` + `COPY` in same txn (current) | ~2.7s |
| `DELETE`; **`COMMIT`**; then `COPY` in a fresh txn | ~3.2s — **no improvement** |
| `DELETE`; `COMMIT`; **`VACUUM`** (15.6s); `COPY` | COPY ~3.0s, but VACUUM costs 15.6s — **net loss** for a few-release run |

- Committing the DELETE before the write does **not** remove the penalty.
- `VACUUM` removes the dead tuples and helps the COPY, but a full-table vacuum
  costs far more than it saves when only a few releases are being recalculated.
- **The penalty scales with bloat.** A freshly-vacuumed table gives ~2.7s for
  the write; after repeated recalc cycles without vacuum it climbs to ~6s. Since
  the cron reruns every 3 hours and only ever deletes+reinserts (no truncate),
  the table stays perpetually somewhat bloated.

## Index cost summary

`player_rating_by_tournament` carries:

- `PRIMARY KEY (id)` (fillfactor 80)
- `UNIQUE (release_id, player_id, tournament_id)` (fillfactor 80)
- `btree (player_id)` (fillfactor 80)
- `FOREIGN KEY (release_id) → release(id)` — `DEFERRABLE INITIALLY DEFERRED`
  (checked at COMMIT, not during the COPY)

Effects:

- Maintaining these three indexes turns a 0.13s heap-only load into a 1.2s load.
- The **unique index is what makes DELETE+reinsert expensive** (dead-entry
  visibility checks).
- The deferred FK is checked once at COMMIT; its cost showed up as a ~1s commit
  in one profile and ~0 in another (variable).

## Other findings

- **`copy.deepcopy` is the single largest cost** in a release calc (~18s),
  entirely in the pure-Python calc phase (`scripts/main.py:59-60`). It is
  unrelated to the write strategy. Replacing it with a vectorized pandas `.copy()`
  (or restructuring to avoid the deep copy) is the biggest available lever.

- **Unchanged releases still pay the full delete+reinsert.** Recalculating
  release 442 produced a hash that **matched** the stored one (the
  `"hashes are different, updating release"` log line never fired), yet
  `dump_release` had already deleted and reinserted ~300k + ~73k byte-identical
  rows. The existing `calculate_hash` fingerprint is only consulted *after* the
  write, to decide whether to bump `updated_at` — never to skip the write.
  For the real workload (recalc the last few releases every 3 hours, where recent
  releases usually have not changed), short-circuiting the write when the hash
  matches would eliminate most of this cost without touching the schema or the
  read path.
  - Caveat: the current hash covers player/team/tournament ratings but not every
    written column (`rating_change`, `place`, `place_change`, bonus detail), so a
    skip-on-match would want the hash widened or accept that purely cosmetic
    column drift would not be re-persisted.
