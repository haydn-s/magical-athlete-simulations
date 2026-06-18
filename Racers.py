#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 10:57:36 2026

@author: kaltmann
"""


from dataclasses import dataclass, field


@dataclass
class Racer:
    name: str
    identifier: int
    powers: list = field(default_factory=list)
    position: int = 0
    finished: bool = False
    eliminated: bool = False
    is_tripped: bool = False
    points: int = 0
    virus_skip_main_turn: bool = False

    def has_power(self, power_type):
        return any(isinstance(power, power_type) for power in self.powers)

    def get_power(self, power_type):
        for power in self.powers:
            if isinstance(power, power_type):
                return power

        return None

class Alchemist(Racer):
    def __init__(self, name, identifier):
        from Powers import AlchemistPower

        super().__init__(name, identifier)
        self.powers = [AlchemistPower(self)]

class Hare(Racer):
    def __init__(self, name, identifier):
        from Powers import HarePower

        super().__init__(name, identifier)
        self.powers = [HarePower(self)]

class Leaptoad(Racer):
    def __init__(self, name, identifier):
        from Powers import LeaptoadPower

        super().__init__(name, identifier)
        self.powers = [LeaptoadPower(self)]

class Banana(Racer):
    def __init__(self, name, identifier):
        from Powers import BananaPower

        super().__init__(name, identifier)
        self.powers = [BananaPower(self)]

class Blimp(Racer):
    def __init__(self, name, identifier):
        from Powers import BlimpPower

        super().__init__(name, identifier)
        self.powers = [BlimpPower(self)]

class BabaYaga(Racer):
    def __init__(self, name, identifier):
        from Powers import BabaYagaPower

        super().__init__(name, identifier)
        self.powers = [BabaYagaPower(self)]

class Coach(Racer):
    def __init__(self, name, identifier):
        from Powers import CoachPower

        super().__init__(name, identifier)
        self.powers = [CoachPower(self)]

class Scoocher(Racer):
    def __init__(self, name, identifier):
        from Powers import ScoocherPower

        super().__init__(name, identifier)
        self.powers = [ScoocherPower(self)]

class Centaur(Racer):
    def __init__(self, name, identifier):
        from Powers import CentaurPower

        super().__init__(name, identifier)
        self.powers = [CentaurPower(self)]

class HugeBaby(Racer):
    def __init__(self, name, identifier):
        from Powers import HugeBabyPower

        super().__init__(name, identifier)
        self.powers = [HugeBabyPower(self)]

class Gunk(Racer):
    def __init__(self, name, identifier):
        from Powers import GunkPower

        super().__init__(name, identifier)
        self.powers = [GunkPower(self)]

class Lackey(Racer):
    def __init__(self, name, identifier):
        from Powers import LackeyPower

        super().__init__(name, identifier)
        self.powers = [LackeyPower(self)]

class Heckler(Racer):
    def __init__(self, name, identifier):
        from Powers import HecklerPower

        super().__init__(name, identifier)
        self.powers = [HecklerPower(self)]

class Skipper(Racer):
    def __init__(self, name, identifier):
        from Powers import SkipperPower

        super().__init__(name, identifier)
        self.powers = [SkipperPower(self)]

class Romantic(Racer):
    def __init__(self, name, identifier):
        from Powers import RomanticPower

        super().__init__(name, identifier)
        self.powers = [RomanticPower(self)]

class HighFive(Racer):
    def __init__(self, name, identifier):
        from Powers import HighFivePower

        super().__init__(name, identifier)
        self.powers = [HighFivePower(self)]

class BlackHole(Racer):
    def __init__(self, name, identifier):
        from Powers import BlackHolePower

        super().__init__(name, identifier)
        self.powers = [BlackHolePower(self)]

class Pendulum(Racer):
    def __init__(self, name, identifier):
        from Powers import PendulumPower

        super().__init__(name, identifier)
        self.powers = [PendulumPower(self)]

class Drafter(Racer):
    def __init__(self, name, identifier):
        from Powers import DrafterPower

        super().__init__(name, identifier)
        self.powers = [DrafterPower(self)]

class Underdog(Racer):
    def __init__(self, name, identifier):
        from Powers import UnderdogPower

        super().__init__(name, identifier)
        self.powers = [UnderdogPower(self)]

class Domino(Racer):
    def __init__(self, name, identifier):
        from Powers import DominoPower

        super().__init__(name, identifier)
        self.powers = [DominoPower(self)]

class Collector(Racer):
    def __init__(self, name, identifier):
        from Powers import CollectorPower

        super().__init__(name, identifier)
        self.powers = [CollectorPower(self)]

class EvenSteven(Racer):
    def __init__(self, name, identifier):
        from Powers import EvenStevenPower

        super().__init__(name, identifier)
        self.powers = [EvenStevenPower(self)]

class OddTodd(Racer):
    def __init__(self, name, identifier):
        from Powers import OddToddPower

        super().__init__(name, identifier)
        self.powers = [OddToddPower(self)]

class Cheerleader(Racer):
    def __init__(self, name, identifier):
        from Powers import CheerleaderPower

        super().__init__(name, identifier)
        self.powers = [CheerleaderPower(self)]

class Legs(Racer):
    def __init__(self, name, identifier):
        from Powers import LegsPower

        super().__init__(name, identifier)
        self.powers = [LegsPower(self)]

class PartyAnimal(Racer):
    def __init__(self, name, identifier):
        from Powers import PartyAnimalPower

        super().__init__(name, identifier)
        self.powers = [PartyAnimalPower(self)]

class Inchworm(Racer):
    def __init__(self, name, identifier):
        from Powers import InchwormPower

        super().__init__(name, identifier)
        self.powers = [InchwormPower(self)]

class Genius(Racer):
    def __init__(self, name, identifier):
        from Powers import GeniusPower

        super().__init__(name, identifier)
        self.powers = [GeniusPower(self)]

class MOUTH(Racer):
    def __init__(self, name, identifier):
        from Powers import MOUTHPower

        super().__init__(name, identifier)
        self.powers = [MOUTHPower(self)]

class RocketScientist(Racer):
    def __init__(self, name, identifier):
        from Powers import RocketScientistPower

        super().__init__(name, identifier)
        self.powers = [RocketScientistPower(self)]

class Duelist(Racer):
    def __init__(self, name, identifier):
        from Powers import DuelistPower

        super().__init__(name, identifier)
        self.powers = [DuelistPower(self)]

class Stickler(Racer):
    def __init__(self, name, identifier):
        from Powers import SticklerPower

        super().__init__(name, identifier)
        self.powers = [SticklerPower(self)]

class Hypnotist(Racer):
    def __init__(self, name, identifier):
        from Powers import HypnotistPower

        super().__init__(name, identifier)
        self.powers = [HypnotistPower(self)]

class FlipFlop(Racer):
    def __init__(self, name, identifier):
        from Powers import FlipFlopPower

        super().__init__(name, identifier)
        self.powers = [FlipFlopPower(self)]

class Suckerfish(Racer):
    def __init__(self, name, identifier):
        from Powers import SuckerfishPower

        super().__init__(name, identifier)
        self.powers = [SuckerfishPower(self)]

class ThirdWheel(Racer):
    def __init__(self, name, identifier):
        from Powers import ThirdWheelPower

        super().__init__(name, identifier)
        self.powers = [ThirdWheelPower(self)]

class Tracker(Racer):
    def __init__(self, name, identifier):
        from Powers import TrackerPower

        super().__init__(name, identifier)
        self.powers = [TrackerPower(self)]

class Gambler(Racer):
    def __init__(self, name, identifier):
        from Powers import GamblerPower

        super().__init__(name, identifier)
        self.powers = [GamblerPower(self)]

class RubberBand(Racer):
    def __init__(self, name, identifier):
        from Powers import RubberBandPower

        super().__init__(name, identifier)
        self.powers = [RubberBandPower(self)]

class Wrangler(Racer):
    def __init__(self, name, identifier):
        from Powers import WranglerPower

        super().__init__(name, identifier)
        self.powers = [WranglerPower(self)]

class Daredevil(Racer):
    def __init__(self, name, identifier):
        from Powers import DaredevilPower

        super().__init__(name, identifier)
        self.powers = [DaredevilPower(self)]

class TrafficCop(Racer):
    def __init__(self, name, identifier):
        from Powers import TrafficCopPower

        super().__init__(name, identifier)
        self.powers = [TrafficCopPower(self)]

class Powerless(Racer):
    def __init__(self, name, identifier):
        from Powers import PowerlessPower

        super().__init__(name, identifier)
        self.powers = [PowerlessPower(self)]

class SixSeven(Racer):
    def __init__(self, name, identifier):
        from Powers import SixSevenPower

        super().__init__(name, identifier)
        self.powers = [SixSevenPower(self)]

class CrossingGuard(Racer):
    def __init__(self, name, identifier):
        from Powers import CrossingGuardPower

        super().__init__(name, identifier)
        self.powers = [CrossingGuardPower(self)]

class MadBomber(Racer):
    def __init__(self, name, identifier):
        from Powers import MadBomberPower

        super().__init__(name, identifier)
        self.powers = [MadBomberPower(self)]

class Magician(Racer):
    def __init__(self, name, identifier):
        from Powers import MagicianPower

        super().__init__(name, identifier)
        self.powers = [MagicianPower(self)]

class LovableLoser(Racer):
    def __init__(self, name, identifier):
        from Powers import LovableLoserPower

        super().__init__(name, identifier)
        self.powers = [LovableLoserPower(self)]

class Sisyphus(Racer):
    def __init__(self, name, identifier):
        from Powers import SisyphusPower

        super().__init__(name, identifier)
        self.powers = [SisyphusPower(self)]

class TripleJump(Racer):
    def __init__(self, name, identifier):
        from Powers import TripleJumpPower

        super().__init__(name, identifier)
        self.powers = [TripleJumpPower(self)]

class Dicemonger(Racer):
    def __init__(self, name, identifier):
        from Powers import DicemongerPower

        super().__init__(name, identifier)
        self.powers = [DicemongerPower(self)]

class Oddball(Racer):
    def __init__(self, name, identifier):
        from Powers import OddballPower

        super().__init__(name, identifier)
        self.powers = [OddballPower(self)]

class Virus(Racer):
    def __init__(self, name, identifier):
        from Powers import VirusPower

        super().__init__(name, identifier)
        self.powers = [VirusPower(self)]