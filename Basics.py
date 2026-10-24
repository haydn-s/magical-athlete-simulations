#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun  7 22:15:14 2026

@author: kaltmann
"""

from Racers import *
from Powers import *
from dataclasses import dataclass, field
import random

DANGER_POWER_TYPES = (
    ScoocherPower,
    RomanticPower,
    HecklerPower,
    FlipFlopPower,
    SkipperPower,
)

@dataclass
class TrackSpace:
    trip: bool = False
    move: int = 0   # +3 arrow, -2 arrow, etc.
    points: int = 0

@dataclass
class SpaceInfo:
    position: int
    track_space: TrackSpace | None
    racers: list
    has_bomb: bool = False
    bomb_owner: Racer | None = None

    @property
    def occupied(self):
        return len(self.racers) > 0

    @property
    def has_trip(self):
        return self.track_space is not None and self.track_space.trip

    @property
    def arrow_move(self):
        if self.track_space is None:
            return 0
        return self.track_space.move

    @property
    def points(self):
        if self.track_space is None:
            return 0
        return self.track_space.points

    @property
    def is_marked(self):
        if self.track_space is None:
            return False
        if self.track_space.points != 0:
            return True
        if self.track_space.move != 0:
            return True
        if self.track_space.trip:
            return True
        return False

@dataclass
class Track:
    name: str = "Unnamed"
    length: int = 30
    spaces: dict[int, TrackSpace] = field(default_factory=dict)

    def resolve_space(self, game, racer):
        effect = self.spaces.get(racer.position)

        if effect is None:
            return

        state = game.get_track_loop_state(racer)

        if state in game.seen_track_states:
            game.log.append(
                f"Track effect loop detected at space {racer.position}; stopping track resolution."
            )
            return

        game.seen_track_states.add(state)

        if effect.trip:
            game.log.append(f"{racer.name} lands on a trip space.")
            game.trip_racer(racer, source="track")

        if effect.move != 0:
            game.log.append(
                f"{racer.name} lands on an arrow and moves {effect.move}."
            )
            game.move_racer(racer, effect.move, source="track")

        if effect.points:
            racer.points += effect.points

            game.log.append(
                f"{racer.name} gains {effect.points} point chip from space {racer.position}."
            )

    def has_finished(self, position: int) -> bool:
        return position >= self.length


@dataclass
class Game:
    racers: list[Racer]
    track: Track
    rng: random.Random = field(default_factory=random.Random)
    turn_index: int = 0
    turn_number: int = 1
    log: list[str] = field(default_factory=list)
    places_to_award: int = 1


    def __init__(self, racers, track, rng=None, places_to_award = 2):
        self.racers = racers
        self.track = track
        self.rng = rng or random.Random()
        self.places_to_award = places_to_award
        self.event_bus = EventBus()
        self.turn_order = list(racers)
        #self.current_turn_index = 0
        self.round_number = 1
        self.phase = "setup"
        self.finished = False
        self.log = []
        self.pending_events = []
        self.power_stack_depth = 0
        self.register_powers()
        self.seen_chain_states = set()
        self.seen_track_states = set()
        self.romantic_seen_states = set()
        self.next_racer_override = None
        self.finish_order = []
        self.duels_this_chain = 0
        self.max_duels_per_chain = 20
        self.bombs = {}  # position -> owner

    def has_danger_power(self, racer):
        return any(
            racer.has_power(power_type)
            for power_type in DANGER_POWER_TYPES
        )

    def get_danger_racers(self):
        return [
            racer for racer in self.get_active_racers()
            if self.has_danger_power(racer)
        ]

    def get_racers_behind_position(self, position, ignore_finished=True):
        racers = self.get_active_racers()

        if ignore_finished:
            racers = [r for r in racers if not r.finished]

        return [r for r in racers if r.position < position]

    def racers_before(self, target):
        start = self.turn_index
        target_index = self.racers.index(target)

        racers = []
        i = (start + 1) % len(self.racers)

        while i != target_index:
            racers.append(self.racers[i])
            i = (i + 1) % len(self.racers)

        return racers

    def inspect_space(self, position, ignore_racer=None):
        return SpaceInfo(
            position=position,
            track_space=self.track.spaces.get(position),
            racers=[
                racer for racer in self.racers
                if racer is not ignore_racer
                   and not racer.finished
                   and not racer.eliminated
                   and racer.position == position
            ],
            has_bomb = position in self.bombs,
            bomb_owner = self.bombs.get(position)
        )

    def get_scores(self):
        return {
            racer.name: racer_score(self, racer)
            for racer in self.racers
        }

    def would_power_activation_finish_scoocher(self):
        for racer in self.racers:
            if racer.finished or racer.eliminated:
                continue

            # ok, not finish, but put within a die roll of finishing
            if racer.has_power(ScoocherPower):
                if racer.position >= self.track.length - 7:
                    return True

        return False

    def would_power_activation_finish_dicemonger(self):
        dicemonger = self.get_active_dicemonger()

        if dicemonger is None:
            return False

        # ok, not finish, but put within a die roll of finishing
        if dicemonger.position >= self.track.length - 7:
            return True

        return False

    def offer_dicemonger_reroll(self, racer, roll):
        dicemonger = self.get_active_dicemonger()

        if dicemonger is None:
            return roll

        power = racer.powers[0] if racer.powers else None

        if power is None:
            should_reroll = roll <= 3
        else:
            should_reroll = power.should_use_dicemonger_reroll(self, roll)

        if not should_reroll:
            return roll

        new_roll = self.roll_die()

        self.log.append(
            f"{racer.name} uses Dicemonger's reroll and gets {new_roll}."
        )

        self.emit(
            DicemongerRerollEvent(
                racer=racer,
                old_value=roll,
                new_value=new_roll
            )
        )

        return new_roll

    def exact_finish_required_for(self, racer):
        if racer.finished or racer.eliminated:
            return False

        # Stickler's card says "other racers", so Stickler is exempt.
        if racer.has_power(SticklerPower):
            return False

        return any(
            other.has_power(SticklerPower)
            and not other.finished
            and not other.eliminated
            for other in self.racers
        )

    def would_overshoot_with_stickler(self, racer, distance):
        if not self.exact_finish_required_for(racer):
            return False

        return distance > 0 and racer.position + distance > self.track.length

    def would_overshoot_finish(self, position):
        return position > self.track.length

    def get_single_active_racer_with_power(self, power_type):
        # will only return 1. Don't look for powers there might be multiple of
        for racer in self.get_active_racers():
            if racer.has_power(power_type):
                return racer
        return None

    def get_active_stickler(self):
        return self.get_single_active_racer_with_power(SticklerPower)

    def prevented_by_stickler(self, racer, attempted_distance):
        stickler = self.get_active_stickler()

        if stickler:
            stickler_power = stickler.get_power(SticklerPower)
            prevented_event = MovePreventedEvent(
                racer=racer,
                attempted_distance=attempted_distance,
                reason="stickler"
            )

            stickler_power.activate_power(
                self,
                prevented_event,
                f"{stickler_power.owner.name}'s Stickler Power prevents {racer.name} from overshooting the finish."
            )

            self.emit(prevented_event)

    def get_active_dicemonger(self):
        return self.get_single_active_racer_with_power(DicemongerPower)

    def get_active_racers(self):
        return [
            racer
            for racer in self.racers
            if not racer.finished
               and not racer.eliminated
        ]

    def get_last_place_racers(self):
        active_racers = [r for r in self.racers if not (r.finished or r.eliminated)]

        if not active_racers:
            return []

        last_position = min(r.position for r in active_racers)

        return [r for r in active_racers if r.position == last_position]

    def mark_finished_if_needed(self, racer):
        if racer.finished or racer.eliminated:
            return

        if self.track.has_finished(racer.position):
            racer.finished = True

            if racer not in self.finish_order:
                self.finish_order.append(racer)

            if len(self.finish_order) == 1:
                racer.points += 5
            if len(self.finish_order) == 2:
                racer.points += 3

            self.log.append(
                f"{racer.name} finishes in place {len(self.finish_order)}!"
            )

    def emit(self, event):
        self.event_bus.emit(self, event)
        return event
    
    def roll_die(self) -> int:
        return self.rng.randint(1, 6)

    def current_racer(self) -> Racer:
        return self.racers[self.turn_index]

    def advance_turn_order(self):
        if self.next_racer_override is not None:
            self.turn_index = self.racers.index(self.next_racer_override)
            self.next_racer_override = None
            return

        self.turn_index = (self.turn_index + 1) % len(self.racers)

    def take_turn(self):
        self.duels_this_chain = 0
        self.seen_chain_states.clear()
        self.seen_track_states.clear()
        self.romantic_seen_states.clear()

        racer = self.current_racer()

        if racer.finished or racer.eliminated:
            self.advance_turn_order()
            return

        turn_start_position = racer.position
        recovered_from_trip = False
        start_roll_event = StartTurnEvent(racer)
        self.emit(start_roll_event)
        self.log.append(f"Turn {self.turn_number}: {racer.name}'s turn.")

        if racer.is_tripped:
            self.log.append(f"{racer.name} recovers from tripping and skips their main move.")
            racer.is_tripped = False
            recovered_from_trip = True

            self.end_turn(
                racer,
                start_position=turn_start_position,
                recovered_from_trip=recovered_from_trip
            )
            return

        if racer.virus_skip_main_turn:
            racer.virus_skip_main_turn = False

            self.log.append(
                f"{racer.name} is affected by Virus and moves 2 instead of taking their main turn."
            )

            self.move_racer(racer, 2, source="main")

            self.end_turn(
                racer,
                start_position=turn_start_position
            )
            return

# BEFORE ROLL
        before_roll_event = BeforeRollEvent(racer)
        self.emit(before_roll_event)
        if before_roll_event.cancelled:
            if before_roll_event.forced_main_distance is not None:
                distance = before_roll_event.forced_main_distance
                self.log.append(f"{racer.name} will move {distance} steps.")
                self.move_racer(racer, distance, source="main")
            self.end_turn(
                racer,
                start_position=turn_start_position
            )
            return


# THE ROLL
        roll = self.roll_die()
        roll_event = RollEvent(racer=racer, value=roll)

        self.log.append(f"{racer.name} rolls {roll}.")
        self.emit(roll_event)

        # Dicemonger reroll chance here
        roll_event.value = self.offer_dicemonger_reroll(racer, roll_event.value)
        self.emit(
            FinalRollEvent(
                racer=racer,
                value=roll_event.value
            )
        )

        if roll_event.main_move_cancelled:
            self.log.append(f"{racer.name}'s main move is skipped.")
            self.end_turn(
                racer,
                start_position=turn_start_position
            )
            return

# BEFORE THE MOVE
        before_main_event = BeforeMainEvent(
            racer=racer,
            distance=roll_event.value
        )
        self.emit(before_main_event)

        self.log.append(f"{racer.name} will move {before_main_event.distance} steps.")

# THE MOVE
        self.move_racer(racer, before_main_event.distance)

        if roll_event.tripped:
            self.trip_racer(racer, source="DaredevilPower")

        self.end_turn(
            racer,
            start_position=turn_start_position
        )

        if self.race_over():
            return

    def move_racer(self, racer, steps, source="main"):
        if steps == 0:
            return

        direction = 1
        if steps < 0:
            direction = -1
            steps = abs(steps)

        stickler = self.get_active_stickler()

        if (
                stickler is not None
                and stickler is not racer
                and direction > 0
                and self.track.has_finished(racer.position + steps)
                and racer.position + steps != self.track.length
        ):
            self.prevented_by_stickler(racer, steps)
            return

            # existing move_racer logic continues...

        move_event = MoveEvent(
            racer=racer,
            steps_remaining=steps,
            direction=direction,
            source=source
        )

        start_position = racer.position

        safety = 100

        while move_event.steps_remaining > 0:
            safety -= 1
            if safety <= 0:
                raise RuntimeError(
                    f"Movement loop exceeded safety limit: {racer.name}, "
                    f"position={racer.position}, steps_remaining={move_event.steps_remaining}"
                )
            if racer.finished or racer.eliminated:
                break

            old_position = racer.position
            new_position = max(
                0,
                racer.position + move_event.direction
            )

            if new_position == racer.position:
                move_event.steps_remaining -= 1
                continue

            enter_space_event = EnterSpaceEvent(
                racer=racer,
                old_position=old_position,
                new_position=new_position,
                move=move_event,
                occupied=self.is_space_occupied(new_position, ignore_racer=racer),
            )
            self.emit(enter_space_event)

            if enter_space_event.cancelled:
                continue

            if self.exact_finish_required_for(racer) and self.would_overshoot_finish(enter_space_event.new_position):
                self.prevented_by_stickler(racer, move_event.steps_remaining)
                return

            racer.position = enter_space_event.new_position
            move_event.steps_remaining -= 1

            self.log.append(
                f"{racer.name} moves from {old_position} to {racer.position}."
            )

            self.mark_finished_if_needed(racer)

            if racer.finished or racer.eliminated:
                break

        # Racer completed movement
        if racer.finished or racer.eliminated:
            return

        land_event = LandOnSpaceEvent(
            racer=racer,
            position=racer.position
        )
        self.emit(land_event)

        if land_event.cancelled:
            return

        self.track.resolve_space(self, racer)

        # Now powers react

        end_position = racer.position
        actual_distance = end_position - start_position

        after_move_event = AfterMoveEvent(
            racer=racer,
            start_position=start_position,
            end_position=end_position,
            move=move_event,
        )
        self.emit(after_move_event)

        if after_move_event.tripped:
            self.trip_racer(racer, source="AfterMoveEvent")

        if source == "main":
            after_main_event = AfterMainEvent(
                racer=racer,
                start_position=start_position,
                end_position=end_position,
                distance=actual_distance,
            )
            self.emit(after_main_event)

            if after_main_event.tripped:
                self.trip_racer(racer, source="AfterMainEvent")

    def is_space_occupied(self, position: int, ignore_racer: Racer | None = None) -> bool:
        return any(
            other is not ignore_racer
            and not other.finished
            and not other.eliminated
            and other.position == position
            for other in self.racers
        )

    def end_turn(self, racer, start_position, recovered_from_trip=False):
        end_turn_event = EndTurnEvent(
            racer=racer,
            start_position=start_position,
            end_position=racer.position,
            recovered_from_trip=recovered_from_trip,
        )
        self.emit(end_turn_event)

        self.turn_number += 1
        self.advance_turn_order()

    def race_over(self):
        if len(self.finish_order) >= self.places_to_award:
            return True

        if len(self.get_active_racers()) == 0:
            return True

        return False

    def run_race(self):
        self.emit(BeforeRaceEvent())
        while not self.race_over() and self.turn_number < 1000:
            self.take_turn()

        return self.get_results()

    def get_results(self):
        results = []

        # Finishers in actual finish order
        results.extend(self.finish_order)

        # Active racers who did not finish
        active = [
            racer
            for racer in self.racers
            if racer not in self.finish_order
               and not racer.eliminated
        ]

        active.sort(key=lambda r: r.position, reverse=True)
        results.extend(active)

        # Eliminated racers last
        eliminated = [
            racer
            for racer in self.racers
            if racer.eliminated
        ]

        eliminated.sort(key=lambda r: r.position, reverse=True)
        results.extend(eliminated)

        return results
    
    def register_powers(self):
        for racer in self.racers:
            for power in racer.powers:
                power.register(self.event_bus)

    def get_leaders(self):
        active_racers = [
            racer
            for racer in self.racers
            if not racer.finished
               and not racer.eliminated
        ]

        if not active_racers:
            return []

        lead_spot = max(r.position for r in active_racers)

        return [
            racer
            for racer in active_racers
            if racer.position == lead_spot
        ]

    def racers_at_position(self, position: int, exclude: Racer | None = None) -> list[Racer]:
        return [
            racer for racer in self.racers
            if racer is not exclude
               and not racer.finished
               and not racer.eliminated
               and racer.position == position
        ]

    def get_loop_state(self):
        return tuple(
            (r.identifier, r.position, r.is_tripped, r.finished, r.eliminated)
            for r in self.racers
        )

    def get_track_loop_state(self, racer):
        return (
            racer.identifier,
            racer.position,
            tuple(
                (r.identifier, r.position, r.is_tripped, r.finished, r.eliminated)
                for r in self.racers
            )
        )

    def trip_racer(self, racer, source=""):
        if racer.is_tripped:
            return

        trip_event = TripEvent(
            racer=racer,
            source=source
        )

        self.emit(trip_event)
        if trip_event.cancelled:
            return

        racer.is_tripped = True

def racer_score(game, racer):
    base = min(racer.position, game.track.length)

    #if racer in game.finish_order:
    #    place = game.finish_order.index(racer) + 1

    #    if place == 1:
    #        base += 5   # winner: 35 max
    #    elif place == 2:
    #        base += 3
    #    elif place == 3:
    #        base += 1

    return base
