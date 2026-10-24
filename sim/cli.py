"""
Command line for the batch simulator.

    python -m sim run -n 100000 --track wild --seed 538
    python -m sim run -n 50000 --focus Oddball
    python -m sim replay --from results/<run> --game 1234
    python -m sim compare results/<run A> results/<run B>
    python -m sim serve
    python -m sim list
"""
import argparse
import os
import sys
import time

from sim import batch, roster, tracks
from sim.runner import setup_game
from sim.stats import SORT_KEYS, two_proportion_z

RESULTS_DIR = batch.RESULTS_DIR


# --- config ------------------------------------------------------------------

def _names(values):
    """Flatten repeated and comma-separated name options."""
    return [n.strip() for v in values or () for n in v.split(",") if n.strip()]


def add_config_args(parser):
    parser.add_argument("--track", default="wild", help=f"track key: {', '.join(tracks.TRACKS)} (default: wild)")
    parser.add_argument("--players", type=int, default=7, help="racers per game (default: 7)")
    parser.add_argument("--places", type=int, default=2, help="finishers before the race ends (default: 2)")
    parser.add_argument("--seed", type=int, help="master seed (default: random, recorded in the results)")
    parser.add_argument("--focus", action="append", metavar="NAME", help="seat this racer in every game (repeatable)")
    parser.add_argument("--include", action="append", metavar="NAME", help="add an opt-in racer or variant to the pool")
    parser.add_argument("--exclude", action="append", metavar="NAME", help="remove a racer from the pool")
    parser.add_argument("--only", action="append", metavar="NAME", help="use exactly these racers as the pool")


def _config_error(exc):
    return SystemExit(f"error: {exc.args[0] if exc.args else exc}")


def config_from_args(args, games):
    try:
        return batch.build_config(
            games=games,
            track=args.track,
            players=args.players,
            places=args.places,
            seed=args.seed,
            focus=_names(args.focus),
            include=_names(args.include),
            exclude=_names(args.exclude),
            only=_names(args.only),
        )
    except (KeyError, ValueError) as exc:
        raise _config_error(exc) from None


def config_from_json(data, games=None):
    try:
        return batch.config_from_json(data, games=games)
    except (KeyError, ValueError) as exc:
        raise _config_error(exc) from None


# --- run ---------------------------------------------------------------------

def cmd_run(args):
    config, replaced = config_from_args(args, args.games)
    if args.no_save:
        out_dir = None
    else:
        out_dir = args.out or batch.default_out_dir(args.label, args.track, config)

    if replaced:
        print(f"Variants racing in place of: {', '.join(replaced)}", file=sys.stderr)

    progress = Progress(config.games)
    summary, _ = batch.execute(
        config,
        track_key=args.track,
        replaced=replaced,
        label=args.label,
        out_dir=out_dir,
        workers=args.workers,
        chunk_size=args.chunk_size,
        save_games=args.save_games,
        sort=args.sort,
        command=" ".join(["python -m sim"] + sys.argv[1:]),
        on_progress=progress.update,
    )
    progress.finish()

    print_summary(summary)
    if out_dir:
        print(f"\nResults saved to {os.path.relpath(out_dir)}")


class Progress:
    def __init__(self, total):
        self.total = total
        self.started = time.time()
        self.tty = sys.stderr.isatty()
        self.next_report = 0.1

    def update(self, done, total):
        rate = done / max(time.time() - self.started, 1e-9)
        line = f"  {done:,} / {total:,} games  ({rate:,.0f} games/s)"
        if self.tty:
            print("\r" + line, end="", file=sys.stderr, flush=True)
        elif done / total >= self.next_report:
            print(line, file=sys.stderr, flush=True)
            self.next_report += 0.1

    def finish(self):
        if self.tty:
            print(file=sys.stderr)


def print_summary(summary):
    manifest = summary["manifest"]
    cfg = manifest["config"]
    totals = summary["totals"]
    rate = totals["games"] / manifest["duration_sec"] if manifest["duration_sec"] else 0

    print(
        f"\n{cfg['track_name']} · {cfg['racers_per_game']} racers/game · {totals['games']:,} games · "
        f"seed {cfg['seed']} · {manifest['duration_sec']:.1f}s ({rate:,.0f} games/s, {manifest['workers']} workers)"
    )
    if cfg["focus"]:
        print(f"Focus: {', '.join(cfg['focus'])}")
    print()

    print(f"{'Racer':16s} {'Games':>7s} {'Pts/G':>6s} {'±95%':>5s}  {'Win%':>5s} {'95% CI':>13s}  "
          f"{'Top' + str(cfg['places_to_award']) + '%':>5s} {'AvgPl':>5s} {'Elim%':>5s} {'Turns':>5s}")
    for r in summary["racers"]:
        lo, hi = r["win_rate_ci"]
        pts_half = (r["pts_ci"][1] - r["pts_ci"][0]) / 2
        print(
            f"{r['name']:16s} {r['games']:7,d} {r['pts_per_game']:6.2f} {pts_half:5.2f}  "
            f"{100 * r['win_rate']:5.1f} [{100 * lo:4.1f}, {100 * hi:4.1f}]  "
            f"{100 * r['podium_rate']:5.1f} {r['avg_place']:5.2f} {100 * r['elim_rate']:5.1f} "
            f"{r['avg_game_turns']:5.1f}"
        )

    seats = "  ".join(f"{s['seat']}: {100 * s['win_rate']:.1f}" for s in summary["seats"])
    print(f"\nWin% by seat (turn order): {seats}")
    print(f"Average game length: {totals['avg_turns']:.1f} turns")
    if totals["stalled"]:
        print(f"Stalled games (hit the 1000-turn cap): {totals['stalled']:,}")
    if totals["errors"]:
        print(f"Games that raised an error: {totals['errors']:,} (excluded from stats; see errors.jsonl, "
              f"replay with `python -m sim replay --from <run dir> --game N`)")


# --- replay ------------------------------------------------------------------

def cmd_replay(args):
    if args.source:
        summary = batch.load_summary(args.source)
        manifest = summary["manifest"]
        config = config_from_json(manifest["config"], games=args.game + 1)
        if manifest.get("code_fingerprint") != batch.code_fingerprint():
            print("Warning: the code has changed since this run, so the replay may differ.", file=sys.stderr)
    else:
        if args.seed is None:
            sys.exit("replay needs --seed (or --from <run dir>).")
        config, _ = config_from_args(args, games=args.game + 1)

    game = setup_game(config, args.game)
    print(f"Game {args.game} · seed {config.seed} · {config.track.name}")
    print("Turn order: " + ", ".join(f"{seat}. {r.name}" for seat, r in enumerate(game.racers, 1)))

    results = game.run_race()

    if not args.no_log:
        print("\nLog:")
        for entry in game.log:
            print(entry)

    print("\nResults:")
    for place, racer in enumerate(results, start=1):
        if racer.finished:
            status = "Finished"
        elif racer.eliminated:
            status = "ELIMINATED"
        else:
            status = f"space {racer.position}"
        print(f"{place}. {racer.name} ({status}) {racer.points} Points")


# --- compare -----------------------------------------------------------------

def _variant_base(name):
    try:
        return roster.lookup(name).variant_of
    except KeyError:
        return None


def cmd_compare(args):
    a, b = batch.load_summary(args.a), batch.load_summary(args.b)
    cfg_a, cfg_b = a["manifest"]["config"], b["manifest"]["config"]

    for key in ("track", "racers_per_game", "places_to_award"):
        if cfg_a[key] != cfg_b[key]:
            print(f"Note: runs differ in {key}: {cfg_a[key]} vs {cfg_b[key]}")

    racers_a = {r["name"]: r for r in a["racers"]}
    racers_b = {r["name"]: r for r in b["racers"]}

    # Pair each racer with itself, and a variant with its base (shown first).
    pairs = [(name, name) for name in racers_b if name in racers_a]
    only_a = sorted(set(racers_a) - set(racers_b))
    only_b = sorted(set(racers_b) - set(racers_a))
    for name_a in list(only_a):
        for name_b in list(only_b):
            if _variant_base(name_b) == name_a or _variant_base(name_a) == name_b:
                pairs.insert(0, (name_a, name_b))
                only_a.remove(name_a)
                only_b.remove(name_b)
                break

    labels = [a_name if a_name == b_name else f"{a_name} → {b_name}" for a_name, b_name in pairs]
    width = max([16] + [len(label) for label in labels])

    print(f"\nA: {args.a}\nB: {args.b}\n")
    print(f"{'Racer':{width}s} {'Games A':>8s} {'Games B':>8s} {'Pts A':>6s} {'Pts B':>6s} {'ΔPts':>6s}  "
          f"{'Win% A':>6s} {'Win% B':>6s} {'ΔWin%':>6s} {'z':>6s}")

    for label, (name_a, name_b) in zip(labels, pairs):
        ra, rb = racers_a[name_a], racers_b[name_b]
        z = two_proportion_z(ra["wins"], ra["games"], rb["wins"], rb["games"])
        flag = " *" if abs(z) >= 1.96 else ""
        print(
            f"{label:{width}s} {ra['games']:8,d} {rb['games']:8,d} {ra['pts_per_game']:6.2f} "
            f"{rb['pts_per_game']:6.2f} {rb['pts_per_game'] - ra['pts_per_game']:+6.2f}  "
            f"{100 * ra['win_rate']:6.1f} {100 * rb['win_rate']:6.1f} "
            f"{100 * (rb['win_rate'] - ra['win_rate']):+6.1f} {z:+6.2f}{flag}"
        )

    if only_a:
        print(f"\nOnly in A: {', '.join(only_a)}")
    if only_b:
        print(f"Only in B: {', '.join(only_b)}")
    print("\n* win-rate difference is significant at 95% (two-proportion z-test)")


# --- list --------------------------------------------------------------------

def cmd_list(args):
    print("Default pool:")
    for entry in roster.default_pool():
        print(f"  {entry.identifier:3d}  {entry.name}")

    opt_in = [e for e in roster.ROSTER.values() if not e.in_default_pool]
    if opt_in:
        print("\nOpt-in (use --include or --focus):")
        for entry in opt_in:
            variant = f"  (variant of {entry.variant_of})" if entry.variant_of else ""
            print(f"  {entry.identifier:3d}  {entry.name}{variant}")

    print("\nTracks:")
    for key, track in tracks.TRACKS.items():
        print(f"  {key:6s} {track.name} ({track.length} spaces, {len(track.spaces)} marked)")


# --- serve -------------------------------------------------------------------

def cmd_serve(args):
    from sim.serve import serve
    serve(host=args.host, port=args.port, results_dir=os.path.abspath(args.results))


# --- entry point -------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m sim", description="Magical Athlete batch simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="simulate many games and summarize per-racer results")
    add_config_args(run)
    run.add_argument("-n", "--games", type=int, default=10000, help="number of games (default: 10000)")
    run.add_argument("-j", "--workers", type=int, help="worker processes (default: all CPU cores)")
    run.add_argument("--chunk-size", type=int, default=500, help="games per work unit (default: 500)")
    run.add_argument("--label", help="name for this run, used in the output folder name")
    run.add_argument("--out", help="output folder (default: results/<timestamp>_<label>)")
    run.add_argument("--no-save", action="store_true", help="print the summary only")
    run.add_argument("--save-games", action="store_true", help="also write every game to games.jsonl")
    run.add_argument("--sort", choices=list(SORT_KEYS), default="pts", help="table order (default: pts)")
    run.set_defaults(func=cmd_run)

    replay = sub.add_parser("replay", help="re-run one game from a batch and print its full log")
    add_config_args(replay)
    replay.add_argument("--game", type=int, required=True, help="game index within the batch")
    replay.add_argument("--from", dest="source", metavar="RUN_DIR", help="take the config from a saved run")
    replay.add_argument("--no-log", action="store_true", help="print only the results")
    replay.set_defaults(func=cmd_replay)

    compare = sub.add_parser("compare", help="compare two saved runs racer by racer")
    compare.add_argument("a", help="baseline run folder (or summary.json)")
    compare.add_argument("b", help="candidate run folder (or summary.json)")
    compare.set_defaults(func=cmd_compare)

    lister = sub.add_parser("list", help="list racers and tracks")
    lister.set_defaults(func=cmd_list)

    server = sub.add_parser("serve", help="browse saved runs in the web viewer")
    server.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    server.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    server.add_argument("--results", default=RESULTS_DIR, help="results folder (default: results/)")
    server.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)
