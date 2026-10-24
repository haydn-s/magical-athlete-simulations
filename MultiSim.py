from Basics import *
from Powers import *
from sim.roster import make_all_racers
from sim.tracks import WILD_WILDS
import random

if __name__ == "__main__":
    # Roster and tracks live in sim/roster.py and sim/tracks.py so new designs are
    # registered once. For large, parallel, reproducible runs use `python -m sim run`.
    Wild = WILD_WILDS

    def simulate_many(n=1000, racers_per_game=7, seed=1):
        rng = random.Random(seed)

        total_score = defaultdict(float)
        games_played = defaultdict(int)
        wins = defaultdict(int)
        points = defaultdict(int)

        for _ in range(n):
            all_racers = make_all_racers()
            racers = rng.sample(all_racers, racers_per_game)
            rng.shuffle(racers)

            game = Game(
                racers=racers,
                track=Wild,
                rng=random.Random(rng.randint(0, 10**12)),
                places_to_award=2,
            )

            game.run_race()

            for racer in racers:
                if not racer.eliminated:
                    score = racer_score(game, racer)
                    total_score[racer.name] += score
                    games_played[racer.name] += 1
                    points[racer.name] += racer.points

            if game.finish_order:
                wins[game.finish_order[0].name] += 1

        rankings = []

        for name in total_score:
            rankings.append({
                "name": name,
                "avg_position": total_score[name] / games_played[name],
                "games": games_played[name],
                "wins": wins[name],
                "pts_per_game": points[name] / games_played[name],
                "win_rate": wins[name] / games_played[name],
            })

        return sorted(rankings, key=lambda x: x["pts_per_game"], reverse=True)



    rankings = simulate_many(n=50000, racers_per_game=7, seed=538)

    for r in rankings:
        print(
            f"{r['name']:15s} "
            f"pts={r['pts_per_game']:.2f} "
            f"avg={r['avg_position']:.2f} "
            f"win%={100*r['win_rate']:.1f} "
            f"games={r['games']}"
        )