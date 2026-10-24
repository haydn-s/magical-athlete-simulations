"""
Registry of racers the simulator can seat in a race.

Adding a new design:
  1. Write its Power in Powers.py as usual (a Racer subclass in Racers.py is optional).
  2. register() it at the bottom of this file. New designs default to opt-in, so they
     only race when asked for with --include or --focus.

Variants (alternate versions of an existing power) pass variant_of=<base name>.
A variant always replaces its base: the two never appear in the same race, which
keeps "base vs variant" runs with the same seed directly comparable.
"""
import difflib
import re
from dataclasses import dataclass

import Powers
import Racers
from Racers import Racer

# Not simulated:
#   Copycat - difficult; Mastermind - pre-race bet; Programmer - not yet;
#   Egg, Twin - no in-race capabilities; Hot Potato - changes players, not a racer;
#   Charlatan - all about player interaction.


class PowerRacer:
    """Builds a plain Racer holding one power, for designs without a Racer subclass."""

    def __init__(self, power_cls):
        self.power_cls = power_cls

    def __call__(self, name, identifier):
        racer = Racer(name, identifier)
        racer.powers = [self.power_cls(racer)]
        return racer

    def __eq__(self, other):
        return isinstance(other, PowerRacer) and other.power_cls is self.power_cls

    def __hash__(self):
        return hash(self.power_cls)


@dataclass(frozen=True)
class RacerEntry:
    name: str
    identifier: int
    build: object  # Racer subclass or PowerRacer, called as build(name, identifier)
    in_default_pool: bool = True
    variant_of: str | None = None

    def make(self):
        return self.build(self.name, self.identifier)


ROSTER: dict[str, RacerEntry] = {}


def _normalize(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def register(name, design, identifier=None, in_default_pool=False, variant_of=None):
    """Add a racer. `design` is a Racer subclass or a Power subclass."""
    if name in ROSTER:
        raise ValueError(f"Racer {name!r} is already registered.")
    if variant_of is not None and variant_of not in ROSTER:
        raise ValueError(f"{name!r} is a variant of unknown racer {variant_of!r}.")
    if isinstance(design, type) and issubclass(design, Powers.Power):
        design = PowerRacer(design)
    if identifier is None:
        identifier = max((e.identifier for e in ROSTER.values()), default=0) + 1

    entry = RacerEntry(name, identifier, design, in_default_pool, variant_of)
    ROSTER[name] = entry
    return entry


def lookup(name):
    """Find a racer by name, ignoring case and punctuation ("mouth" -> "M.O.U.T.H.")."""
    by_key = {_normalize(n): e for n, e in ROSTER.items()}
    entry = by_key.get(_normalize(name))
    if entry is None:
        close = difflib.get_close_matches(name, ROSTER.keys(), n=3)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise KeyError(f"Unknown racer {name!r}.{hint}")
    return entry


def default_pool():
    return [e for e in ROSTER.values() if e.in_default_pool]


def build_pool(only=(), include=(), exclude=(), focus=()):
    """
    Resolve CLI-style selections into (pool, focus, replaced).

    pool     - entries that can fill the open seats (never contains a focus racer)
    focus    - entries seated in every race
    replaced - base racers dropped because one of their variants is racing
    """
    pool = [lookup(n) for n in only] if only else default_pool()
    pool += [lookup(n) for n in include]
    focus = [lookup(n) for n in focus]
    excluded = {lookup(n).name for n in exclude}

    racing = pool + focus
    replaced = sorted({e.variant_of for e in racing if e.variant_of})
    focus_names = {e.name for e in focus}

    resolved = []
    for entry in pool:
        if entry.name in excluded or entry.name in replaced or entry.name in focus_names:
            continue
        if entry not in resolved:
            resolved.append(entry)

    return resolved, focus, replaced


_STANDARD = [
    (Racers.Alchemist, "Alchemist", 1),
    (Racers.Banana, "Banana", 2),
    (Racers.Hare, "Hare", 3),
    (Racers.Leaptoad, "Leaptoad", 4),
    (Racers.Blimp, "Blimp", 5),
    (Racers.BabaYaga, "BabaYaga", 6),
    (Racers.Coach, "Coach", 7),
    (Racers.Scoocher, "Scoocher", 8),
    (Racers.Centaur, "Centaur", 9),
    (Racers.HugeBaby, "HugeBaby", 10),
    (Racers.Gunk, "Gunk", 11),
    (Racers.Lackey, "Lackey", 12),
    (Racers.Heckler, "Heckler", 13),
    (Racers.Skipper, "Skipper", 14),
    (Racers.Romantic, "Romantic", 15),
    (Racers.HighFive, "HighFive", 16),
    (Racers.BlackHole, "BlackHole", 17),
    (Racers.Pendulum, "Pendulum", 18),
    (Racers.Drafter, "Drafter", 19),
    (Racers.Underdog, "Underdog", 20),
    (Racers.Domino, "Domino", 21),
    (Racers.Collector, "Collector", 22),
    (Racers.OddTodd, "OddTodd", 23),
    (Racers.EvenSteven, "EvenSteven", 24),
    (Racers.Cheerleader, "Cheerleader", 25),
    (Racers.Legs, "Legs", 26),
    (Racers.PartyAnimal, "PartyAnimal", 27),
    (Racers.Inchworm, "Inchworm", 28),
    (Racers.Genius, "Genius", 29),
    (Racers.MOUTH, "M.O.U.T.H.", 30),
    (Racers.RocketScientist, "RocketScientist", 31),
    (Racers.Duelist, "Duelist", 32),
    (Racers.Stickler, "Stickler", 33),
    (Racers.Hypnotist, "Hypnotist", 34),
    (Racers.FlipFlop, "FlipFlop", 35),
    (Racers.Suckerfish, "Suckerfish", 36),
    (Racers.ThirdWheel, "ThirdWheel", 37),
    (Racers.Tracker, "Tracker", 38),
    (Racers.Gambler, "Gambler", 39),
    (Racers.RubberBand, "RubberBand", 40),
    (Racers.Wrangler, "Wrangler", 41),
    (Racers.Daredevil, "Daredevil", 42),
    (Racers.TrafficCop, "TrafficCop", 43),
    (Racers.Powerless, "Powerless", 44),
    (Racers.SixSeven, "SixSeven", 45),
    (Racers.CrossingGuard, "CrossingGuard", 46),
    (Racers.MadBomber, "MadBomber", 47),
    (Racers.Magician, "Magician", 48),
    (Racers.LovableLoser, "LovableLoser", 49),
    (Racers.Sisyphus, "Sisyphus", 50),
    (Racers.TripleJump, "TripleJump", 51),
    (Racers.Dicemonger, "Dicemonger", 52),
    (Racers.Oddball, "Oddball", 53),
    (Racers.Virus, "Virus", 54),
]

for _cls, _name, _identifier in _STANDARD:
    register(_name, _cls, identifier=_identifier, in_default_pool=True)

# --- Variants and new designs (opt-in) ---------------------------------------

register("ScoocherWeakened", Powers.ScoocherPowerWeakened, variant_of="Scoocher")
