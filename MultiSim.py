from Basics import *
from Powers import *
import random

if __name__ == "__main__":
    Mild = Track(name = "Mild Mile", length=30, spaces={})
    Wild = Track(name = "Wild Wilds", length=30,
                    spaces={
                        1: TrackSpace(points=1),
                        5: TrackSpace(trip=True),
                        7: TrackSpace(move=3),
                        11: TrackSpace(move=1),
                        13: TrackSpace(points=1),
                        16: TrackSpace(move=-4),
                        17: TrackSpace(trip=True),
                        23: TrackSpace(move=2),
                        24: TrackSpace(move=-2),
                        26: TrackSpace(trip=True),
                    }
        )

    # No Copycat - difficult
    # No Mastermind - pre race bet
    # No Programmer - yet
    # No Egg or Twin - they have no in race capabilities
    # No Hot Potato - not a racer, more a player changer
    # No Charlatan - All about player interaction

    def make_all_racers():
        return [
            Alchemist("Alchemist", 1),
            Banana("Banana", 2),
            Hare("Hare", 3),
            Leaptoad("Leaptoad", 4),
            Blimp("Blimp", 5),
            BabaYaga("BabaYaga", 6),
            Coach("Coach", 7),
            Scoocher("Scoocher", 8),
            Centaur("Centaur", 9),
            HugeBaby("HugeBaby", 10),
            Gunk("Gunk", 11),
            Lackey("Lackey", 12),
            Heckler("Heckler", 13),
            Skipper("Skipper", 14),
            Romantic("Romantic", 15),
            HighFive("HighFive", 16),
            BlackHole("BlackHole", 17),
            Pendulum("Pendulum", 18),
            Drafter("Drafter", 19),
            Underdog("Underdog", 20),
            Domino("Domino", 21),
            Collector("Collector", 22),
            OddTodd("OddTodd", 23),
            EvenSteven("EvenSteven", 24),
            Cheerleader("Cheerleader", 25),
            Legs("Legs", 26),
            PartyAnimal("PartyAnimal", 27),
            Inchworm("Inchworm", 28),
            Genius("Genius", 29),
            MOUTH("M.O.U.T.H.", 30),
            RocketScientist("RocketScientist", 31),
            Duelist("Duelist", 32),
            Stickler("Stickler", 33),
            Hypnotist("Hypnotist", 34),
            FlipFlop("FlipFlop", 35),
            Suckerfish("Suckerfish", 36),
            ThirdWheel("ThirdWheel", 37),
            Tracker("Tracker", 38),
            Gambler("Gambler", 39),
            RubberBand("RubberBand", 40),
            Wrangler("Wrangler", 41),
            Daredevil("Daredevil", 42),
            TrafficCop("TrafficCop", 43),
            Powerless("Powerless", 44),
            SixSeven("SixSeven", 45),
            CrossingGuard("CrossingGuard", 46),
            MadBomber("MadBomber", 47),
            Magician("Magician", 48),
            LovableLoser("LovableLoser", 49),
            Sisyphus("Sisyphus", 50),
            TripleJump("TripleJump", 51),
            Dicemonger("Dicemonger", 52),
            Oddball("Oddball", 53),
            Virus("Virus", 54),
        ]


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