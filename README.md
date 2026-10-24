# Magical Athlete Simulations

A simulation of the board game Magical Athlete, built to test our own racer designs
against the standard racers.

| File | What it holds |
| --- | --- |
| `Basics.py` | `Game` (turn loop, movement, finishing) and `Track` |
| `Events.py` | The event bus and event types that powers hook into |
| `Powers.py` | Every racer's power and its in-race decision logic |
| `Racers.py` | Racer classes (one per power) |
| `sim/` | Batch simulator: parallel, reproducible runs with saved results |
| `web/` | Results viewer: a React app for browsing and comparing saved runs |
| `MultiSim.py` | The original single-process batch script (still works) |

The simulator needs Python 3.10+ and the standard library only. The results viewer
also needs Node.js 22.12 or newer.

## Running simulations

```bash
python -m sim run -n 100000 --seed 538
```

That runs 100,000 seven-racer games on Wild Wilds across all CPU cores, prints a
per-racer table, and saves results to `results/<timestamp>_<label>/`. Every game is
determined by `(seed, game number)`, so the same seed gives the same results on any
machine and with any number of workers, as long as the Python version is the same.
If you leave out `--seed`, a random one is picked and recorded.

| Option | Default | |
| --- | --- | --- |
| `-n, --games` | 10000 | games to simulate |
| `--track` | `wild` | `wild` or `mild` (see `sim/tracks.py`) |
| `--players` | 7 | racers per game |
| `--places` | 2 | finishers before the race ends (5 and 3 point chips) |
| `--focus NAME` | | seat this racer in every game (repeatable) |
| `--include NAME` | | add an opt-in design or variant to the pool |
| `--exclude NAME` | | remove a racer from the pool |
| `--only NAME,...` | | use exactly these racers as the pool |
| `-j, --workers` | all cores | worker processes |
| `--label` | | name used in the results folder |
| `--save-games` | off | also write every game to `games.jsonl` |
| `--no-save` | off | print the table only |
| `--sort` | `pts` | `pts`, `win`, `place` or `name` |

Racer names ignore case and punctuation, so `--focus mouth` finds M.O.U.T.H.
`python -m sim list` shows every racer and track.

### Investigating one game

```bash
python -m sim replay --from results/<run folder> --game 1234
```

This re-runs game 1234 of that batch and prints its full turn-by-turn log. It
warns you if the engine or roster has changed since the run. To watch the same
game on an animated board, open the run in the [results viewer](#results-viewer)
and choose **Watch a game**.

### Comparing two runs

```bash
python -m sim compare results/<baseline> results/<candidate>
```

This prints each racer's points and win rate side by side, with the change and a
z-score. A `*` marks win-rate changes that are significant at 95%.

## Results viewer

Build the viewer once (and again after pulling UI changes), then serve it:

```bash
cd web && npm install && npm run build
```

```bash
python -m sim serve
```

Then open the address it prints (`http://127.0.0.1:8000`; pass `--port` to change
it). The server only listens on your own machine. It reads `results/`, and writes
there only when you start a run from the viewer. You get:

- **Runs:** every saved run with its track, size, focus racers and seed. Tick two
  runs to compare them.
- **Leaderboard:** points per game and win rate with 95% intervals drawn inline,
  against the field average and parity. Every column sorts, and there's a filter.
- **Head-to-head:** a heatmap of how often each racer finished ahead of each
  other racer. Hover for the numbers, click to open a racer.
- **Turn order:** win rate by seat.
- **Racer:** headline stats, finishing-place distribution, every matchup, and a
  list of games that racer was in.
- **Game replay:** watch any game from a run, turn by turn. Racers move around an
  animated board (arrows, trip spaces, point spaces, Mad Bomber's bombs and the
  Crossing Guard's crosswalk included) with the game log alongside. Step a line or
  a turn at a time, play at up to 8× speed, scrub, or click a log line to jump
  there. Keys: ←/→ step, Shift+←/→ jump a turn, Space plays. Games that crashed
  are linked from their run, so you can watch them fail.
- **Compare:** racer-by-racer changes between two runs, flagging the significant
  ones and pairing each variant with its base racer.
- **New run:** start a batch from the browser. Pick the track, games, seed, focus
  racers and pool, and see the equivalent `python -m sim run` command as you go.
- **Jobs:** live progress for runs started from the viewer, with cancel, and links
  to the results when they finish.

Every chart has a table view or CSV download, and the viewer follows your
light/dark setting.

### Testing a variant without the command line

1. Open the run you want as the baseline (for example a `--focus Pendulum` run)
   and choose **New run from this**. The form copies its settings, including the
   seed.
2. Swap the focus racer for your variant and choose **Start run**.
3. When the job finishes, choose **Compare with the original**.

Runs started this way go through the same code as `python -m sim run`, so the same
settings and seed give identical results either way. Runs execute one at a time,
each using every core. Cancelling a run stops it within a second or so and keeps
nothing.

To work on the UI with hot reload, run `python -m sim serve` in one terminal and
`npm run dev` in `web/` in another. Vite forwards `/api` requests to port 8000; set
`SIM_API=http://127.0.0.1:<port>` if the server is somewhere else. `npm test` runs
the unit tests, and `npm run typecheck` checks types.

## Testing a new design

1. Write the power in `Powers.py` as usual. A matching class in `Racers.py` is
   optional.
2. Register it at the bottom of `sim/roster.py`:
   ```python
   register("Comet", Powers.CometPower)
   ```
3. Race it against the standard field:
   ```bash
   python -m sim run -n 50000 --focus Comet --seed 1
   ```
   `--focus` puts the racer in every game, so you get many more games for it than
   if it rotated in with everyone else.

### Tuning a variant of an existing racer

Register the variant with `variant_of`:

```python
register("PendulumV2", Powers.PendulumPowerV2, variant_of="Pendulum")
```

A variant always replaces its base racer, so the two never share a race. Run each
one as the focus racer with the **same seed**. Both runs then use identical
opponents, seats and starting dice, and only the power differs. Then compare:

```bash
python -m sim run -n 50000 --seed 7 --focus Pendulum   --label pendulum
python -m sim run -n 50000 --seed 7 --focus PendulumV2 --label pendulum-v2
python -m sim compare results/*_pendulum results/*_pendulum-v2
```

Tip: subclass the base power (`class PendulumPowerV2(PendulumPower)`) unless the
variant should look like a different racer. Other racers' decision logic checks
for specific powers (Hypnotist targets Scoocher and Romantic; many powers hold
back when a Scoocher is near the finish). `ScoocherPowerWeakened` doesn't subclass
`ScoocherPower`, so those checks don't see it as a Scoocher.

## Results files

| File | Contents |
| --- | --- |
| `summary.json` | Everything below, plus a `manifest` with the exact config, seed, roster, git commit and duration |
| `racers.csv` | One row per racer: games, wins, rates with 95% confidence intervals, points, placing |
| `head_to_head.csv` | How often the row racer placed ahead of the column racer when both raced |
| `errors.jsonl` | Games that raised an exception, with lineups (replay them to debug) |
| `games.jsonl` | Every game's lineup and outcome (only with `--save-games`, about 150 MB per million games) |

### Reading the table

- **Pts/G**: average point chips per game (5 for first, 3 for second, plus track
  and power chips), with its 95% margin. This is the main ranking, as in
  `MultiSim.py`.
- **Win%**: share of games the racer finished first, with a 95% Wilson interval.
  If two racers' intervals overlap, run more games before ranking them.
- **TopN%**: finished in a scoring place.
- **AvgPl**: average final placing. Finishers come first in finish order, then
  the others by position, then eliminated racers.
- **Elim%**: share of games the racer was eliminated (M.O.U.T.H.).
- **Turns**: average game length when this racer is in the race. A high number
  means the racer drags games out.
- **Win% by seat**: turn-order advantage across all games.

## How this differs from `MultiSim.py`

- **Reproducible.** Duelist, Flip Flop and Genius use Python's global `random`
  rather than the game's seeded RNG, so `seed=538` never fully pinned down
  MultiSim's results. The new runner seeds that RNG for every game. No power
  code was changed.
- **Eliminated racers count.** MultiSim skipped a racer's game entirely when it
  was eliminated, which slightly inflated win rates for racers that are often
  eliminated. The new runner counts those games at the racer's actual placing
  and points.
- **`avg` was track progress, not placing.** MultiSim's `avg` column is
  `min(position, 30)`. It's kept as `avg_progress` in `racers.csv`, and AvgPl is
  the true placing.
- **A crashing game doesn't stop the batch.** It's logged to `errors.jsonl` and
  left out of the stats.
- **Faster.** The engine runs about 800 games/s per core. 50,000 games took
  about 60s in MultiSim and about 5s on 18 cores.

## Known track assumptions

Some powers hard-code positions for a 30-space track: Crossing Guard's crosswalk
(27), Mad Bomber's bombs (8, 20, 29), High Five (multiples of 5) and Blimp's
halfway point (15). New tracks of other lengths will run, but those racers won't
play as designed.

## Tests

```bash
python -m unittest discover tests
```

These cover the harness, not racer mechanics:

- determinism across seeds, worker counts and hash seeds
- focus and variant lineups
- consistent stats and error capture
- the viewer's API: rejecting paths outside `results/`, and requests a web page
  could forge
- runs started from the viewer: validation, cancelling, and results that match
  the CLI
- game replays: the same placings and points as the batch, one frame per log line
- an end-to-end test of `python -m sim serve` (runs once `web/dist` is built)

The viewer's own tests run with `npm test` in `web/`.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:

| Job | Checks |
| --- | --- |
| Python 3.10 / 3.12 / 3.14 | the unit tests, plus a CLI smoke run of `run`, `replay` and `compare` |
| Web app | `npm ci`, typecheck, unit tests and production build. The built viewer is uploaded as the `results-viewer` artifact (kept 14 days). |
| End-to-end | the real `python -m sim serve` with that build: load the app, start a run through the API, read its results back |
