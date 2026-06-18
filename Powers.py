#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 10:55:01 2026

@author: kaltmann

"""

from Events import *
from collections import Counter
import random

from Racers import Racer


class Power:
    def __init__(self, owner):
        self.owner = owner

    def inactive(self):
        return self.owner.finished or self.owner.eliminated

    def register(self, bus):
        pass

    def log_power(self, game, message):
        game.log.append(message)

    def activate_power(self, game, source_event, message):
        state = game.get_loop_state()

        key = (
            self.owner.identifier,
            type(self).__name__,
            type(source_event).__name__,
            state,
        )

        if key in game.seen_chain_states:
            game.log.append(
                f"Loop detected at {self.owner.name}'s {type(self).__name__}; ending repeated loop."
            )
            return

        game.seen_chain_states.add(key)

        game.log.append(message)

        game.emit(
            PowerActivatedEvent(
                owner=self.owner,
                power=self,
                source_event=source_event,
            )
        )


    def should_use_dicemonger_reroll(self, game, roll):
        spaces_left = game.track.length - self.owner.position

        # Keep a roll that wins.
        if roll == spaces_left:
            return False

        if game.would_power_activation_finish_dicemonger():
            return False

        if game.would_power_activation_finish_scoocher():
            return False

        # If exact finish is required, reroll overshoots.
        if game.exact_finish_required_for(self.owner) and roll > spaces_left:
            return True

        # Basic EV rule.
        return roll <= 3

    
class AlchemistPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main, priority=-10)

    def should_use_dicemonger_reroll(self, game, roll):
        # Alchemist likes 1 and 2 because they become 4.
        if game.would_power_activation_finish_dicemonger():
            return False
        if game.would_power_activation_finish_scoocher():
            return False
        return roll == 3

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer.identifier != self.owner.identifier:
            return

        if event.distance in [1, 2]:
            if game.would_overshoot_with_stickler(self.owner, 4):
                return

            original_distance = event.distance
            event.distance = 4

            self.activate_power(
                game,
                event,
                f"{event.racer.name} uses Alchemist Power to change {original_distance} to 4."
            )

class BabaYagaPower(Power):
    def register(self, bus):
        bus.on(AfterMainEvent, self.after_main)

    def after_main(self, game, event):
        if self.inactive():
            return
        baba = self.owner

        if event.racer is baba:
            # Baba stopped on someone else's space
            for other in game.racers_at_position(baba.position, exclude=baba):
                game.trip_racer(other, source="Baba Yaga")
                #other.is_tripped = True
                self.activate_power(
                    game,
                    event,
                    f"{baba.name} trips {other.name} by stopping on their space."
                )
        else:
            # Someone else stopped on Baba's space
            if event.racer.position == baba.position and not baba.finished and not baba.eliminated :
                game.trip_racer(event.racer, source="Baba Yaga")
                #event.racer.is_tripped = True
                self.activate_power(
                    game,
                    event,
                    f"{event.racer.name} trips by stopping on {baba.name}'s space."
                )

class BananaPower(Power):
    def register(self, bus):
        bus.on(AfterMainEvent, self.after_main)

    def after_main(self, game, event):
        if self.inactive():
            return
        if event.racer.identifier == self.owner.identifier:
            return

        banana_position = self.owner.position

        if event.start_position < banana_position < event.end_position:
            game.trip_racer(event.racer, source="Banana")
            #event.racer.is_tripped = True
            self.activate_power(
                game,
                event,
                f"{event.racer.name} trips after passing {self.owner.name}."
            )

class BlackHolePower(Power):
    def register(self, bus):
        bus.on(AfterMoveEvent, self.after_move, priority=-10)

    def after_move(self, game, event):
        if self.inactive():
            return
        black_hole = self.owner

        if black_hole.finished or black_hole.eliminated:
            return

        # Case 1: Black Hole moved.
        # Carry tripped racers that started on Black Hole's old space.
        if event.racer is black_hole:
            delta = event.end_position - event.start_position

            if delta == 0:
                return

            for other in game.racers:
                if other is black_hole or other.finished or other.eliminated:
                    continue

                if other.is_tripped and other.position == event.start_position:
                    old_position = other.position
                    other.position = max(0, other.position + delta)

                    self.activate_power(
                        game,
                        event,
                        f"{black_hole.name} carries tripped {other.name} from {old_position} to {other.position}."
                    )

            return

        # Case 2: Another racer ended movement near Black Hole.
        mover = event.racer

        if mover.finished or mover.eliminated:
            return

        if abs(mover.position - black_hole.position) > 1:
            return

        # Huge Baby exception:
        # Huge Baby cannot share Black Hole's space.
        # If Huge Baby is within 1, Black Hole trips it but does not pull it.
        if mover.has_power(HugeBabyPower):
            #mover.is_tripped = True
            game.trip_racer(mover, source="Black Hole")
            self.activate_power(
                game,
                event,
                f"{mover.name} is tripped by {black_hole.name}, but cannot be pulled onto {black_hole.name}'s space."
            )
            return

        old_position = mover.position
        mover.position = black_hole.position
        game.trip_racer(mover, source="Black Hole")
        ##mover.is_tripped = True

        self.activate_power(
            game,
            event,
            f"{mover.name} is pulled from {old_position} onto {black_hole.name}'s space and is tripped."
        )

class BlimpPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main)

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer.identifier != self.owner.identifier:
            return

        original_distance = event.distance
        if self.owner.position < 15:
            event.distance += 3
            self.activate_power(
                game,
                event,
                f"{event.racer.name} uses Blimp Power to change {original_distance} to {event.distance}."
            )
        else:
            event.distance -= 1
            self.activate_power(
                game,
                event,
                f"{event.racer.name} uses Blimp Power to change {original_distance} to {event.distance}."
            )

class CentaurPower(Power):
    def register(self, bus):
        bus.on(AfterMainEvent, self.after_main)

    def after_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        start = event.start_position
        end = event.end_position

        for other in game.racers:
            if other is self.owner or other.finished or other.eliminated:
                continue

            if start < other.position < end:
                old_position = other.position
                other.position = max(0, other.position - 2)

                self.activate_power(
                    game,
                    event,
                    f"{self.owner.name} hoofwhacks {other.name} from {old_position} to {other.position}."
                )

class CheerleaderPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main)

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        last_place_racers = game.get_last_place_racers()

        if not last_place_racers:
            return

        if self.owner in last_place_racers:
            should_cheer = True
        else:
            # only cheer others if they are not close to finishing
            should_cheer = not any(
                r.position >= game.track.length - 3
                for r in last_place_racers
            )

        if not should_cheer or game.would_power_activation_finish_scoocher():
            return

        if game.would_overshoot_with_stickler(self.owner, 2):
            return

        for racer in last_place_racers:
            game.move_racer(racer, 2, source="power")

        self.activate_power(
            game,
            event,
            f"{self.owner.name} cheers for last place and moves 1."
        )

        game.move_racer(self.owner, 1, source="power")

class CoachPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main)

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer.position == self.owner.position:
            event.distance += 1
            self.activate_power(
                game,
                event,
                f"{event.racer.name} gains +1 from {self.owner.name}'s Coach Power."
            )

class CollectorPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.rolls_seen = set()
        self.can_move_this_turn = True

    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)
        bus.on(RollEvent, self.after_roll)
        bus.on(BeforeMainEvent, self.before_main)
        bus.on(DicemongerRerollEvent, self.after_dicemonger_reroll)

    def after_dicemonger_reroll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        self.collect_roll(game, event, event.new_value)

    def before_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if len(self.rolls_seen) < 5:
            return

        distance = min(15, game.track.length - self.owner.position)

        event.cancelled = True
        event.forced_main_distance = distance

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Collector Power to move {distance} instead of rolling."
        )

    def should_use_dicemonger_reroll(self, game, roll):
        # Keep any new number, even if it is low.
        if roll not in self.rolls_seen:
            return False
        # Reroll duplicates because they give no movement.
        return True

    def after_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        self.collect_roll(game, event, event.value)
        '''if event.value in self.rolls_seen:
            self.can_move_this_turn = False
            return

        self.rolls_seen.add(event.value)
        self.can_move_this_turn = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} collects a new roll: {event.value}."
        )'''

    def collect_roll(self, game, event, value):
        if value in self.rolls_seen:
            self.can_move_this_turn = False
            return

        self.rolls_seen.add(value)
        self.can_move_this_turn = True

        game.log.append(
            f"{self.owner.name} collects a new roll: {value}. Collected: {sorted(self.rolls_seen)}."
        )

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if not self.can_move_this_turn:
            self.activate_power(
                game,
                event,
                f"{self.owner.name} has already rolled {event.distance} and does not move."
            )
            event.distance = 0

class CrossingGuardPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.crosswalk_position = None

    def register(self, bus):
        bus.on(BeforeRaceEvent, self.before_race)
        bus.on(EnterSpaceEvent, self.enter_space, priority=-20)

    def before_race(self, game, event):
        empty_spaces = [
            position for position in range(1, game.track.length)
            if not game.inspect_space(position).is_marked
        ]

        if not empty_spaces:
            return

        # Simple AI: put it just before the finish if possible.
        #self.crosswalk_position = max(empty_spaces)
        self.crosswalk_position = 27

        game.log.append(f"{self.owner.name} marks space {self.crosswalk_position} as the Crosswalk.")

    def enter_space(self, game, event):
        if self.inactive():
            return

        if self.crosswalk_position is None:
            return

        if event.racer is self.owner:
            return

        if self.guard_is_near_crosswalk():
            return

        old_position = event.old_position
        new_position = event.new_position

        if event.move.direction <= 0:
            return

        if old_position < self.crosswalk_position <= new_position:
            event.new_position = self.crosswalk_position
            event.move.steps_remaining = 1

            self.activate_power(
                game,
                event,
                f"{self.owner.name}'s Crossing Guard Power stops {event.racer.name} at the Crosswalk."
            )

    def guard_is_near_crosswalk(self):
        return abs(self.owner.position - self.crosswalk_position) <= 1

class DaredevilPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        total_bonus = 0
        previous_roll = event.value
        current_total = event.value
        will_trip = False

        while self.should_roll_again(game, previous_roll, current_total):
            new_roll = game.roll_die()
            current_total += new_roll
            total_bonus += new_roll

            game.log.append(
                f"{self.owner.name} uses Daredevil Power and rolls {new_roll}."
            )

            if new_roll <= previous_roll:
                will_trip = True
                break

            previous_roll = new_roll

        if total_bonus == 0:
            return

        old_value = event.value
        event.value = current_total

        if will_trip:
            event.tripped = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name}'s Daredevil Power changes {old_value} to {event.value}."
        )

        if will_trip:
            game.log.append(f"{self.owner.name} will trip after moving.")

    def should_roll_again(self, game, previous_roll, current_total):
        projected_position = self.owner.position + current_total
        if game.would_power_activation_finish_scoocher():
            return False

        spaces_left = game.track.length - projected_position

        if game.exact_finish_required_for(self.owner):
            return 1 <= spaces_left <= 6 and previous_roll < spaces_left

        if projected_position >= game.track.length - 3:
            return True

        return previous_roll < 5

class DicemongerPower(Power):
    def register(self, bus):
        bus.on(DicemongerRerollEvent, self.after_dicemonger_reroll)

    def after_dicemonger_reroll(self, game, event):
        if self.inactive():
            return

        if event.racer is self.owner:
            return

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Dicemonger Power because {event.racer.name} rerolled."
        )

        game.move_racer(self.owner, 1, source="power")

class DominoPower(Power):
    def register(self, bus):
        bus.on(TripEvent, self.trip)

    def trip(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        takedown = False
        # spread left
        pos = self.owner.position - 1
        while game.is_space_occupied(pos):
            for racer in game.racers_at_position(pos):
                game.trip_racer(racer, source="Domino")
                game.log.append(f"{racer.name} is knocked over by {self.owner.name}.")
                takedown = True
            pos -= 1

        # spread right
        pos = self.owner.position + 1
        while game.is_space_occupied(pos):
            for racer in game.racers_at_position(pos):
                game.trip_racer(racer, source="Domino")
                game.log.append(f"{racer.name} is knocked over by {self.owner.name}.")
                takedown = True
            pos += 1

        if takedown:
            event.cancelled = True
            self.activate_power(
                game,
                event,
                f"{self.owner.name} avoids a trip by taking nearby racers out."
            )

class DrafterPower(Power):
    def register(self, bus):
        bus.on(AfterMainEvent, self.after_main)

    def after_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        ahead = [
            racer.position
            for racer in game.racers
            if racer is not self.owner
               and not racer.finished
               and not racer.eliminated
               and racer.position > self.owner.position
        ]

        if not ahead:
            return

        next_ahead = min(ahead)

        empty_spaces = next_ahead - self.owner.position - 1

        if empty_spaces in [1, 2]:
            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Drafter Power to move {empty_spaces}."
            )

            game.move_racer(self.owner, empty_spaces, source="power")

class DuelistPower(Power):
    def register(self, bus):
        bus.on(StartTurnEvent, self.duel_if_sharing)
        bus.on(AfterMoveEvent, self.duel_if_sharing)

    def duel_if_sharing(self, game, event):
        if self.inactive():
            return

        if game.would_overshoot_with_stickler(self.owner, 2):
            return

        if game.would_power_activation_finish_scoocher():
            return

        # If winning the duel is bad, don't do it
        landing_position = self.owner.position + 2
        info = game.inspect_space(landing_position, ignore_racer=self.owner)
        if info.has_trip:
            return
        if info.arrow_move < 0:
            return
        if info.has_bomb:
            return False

        opponents = [
            racer for racer in game.racers
            if racer is not self.owner
            and not racer.finished
            and not racer.eliminated
            and racer.position == self.owner.position
        ]

        if not opponents:
            return

        if game.duels_this_chain >= game.max_duels_per_chain:
            game.log.append(f"{self.owner.name}'s duel chain stops after too many duels.")
            return

        game.duels_this_chain += 1
        opponent = random.choice(opponents)
        self.duel(game, event, opponent)

    def duel(self, game, source_event, opponent):
        duelist_roll = game.roll_die()
        opponent_roll = game.roll_die()

        game.log.append(
            f"DUEL!! between {self.owner.name} and {opponent.name}: "
            f"{self.owner.name} rolls {duelist_roll}, {opponent.name} rolls {opponent_roll}."
        )

        if duelist_roll >= opponent_roll:
            winner = self.owner
        else:
            winner = opponent

        self.activate_power(
            game,
            source_event,
            f"{winner.name} wins the duel and moves 2."
        )

        game.move_racer(winner, 2, source="power")

class EvenStevenPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main, priority=-10)
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is self.owner:
            return

        if event.value % 2 == 0 and event.racer.has_power(OddToddPower):
            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Even Steven Power to move on {event.racer.name}'s even roll."
            )
            game.move_racer(self.owner, event.value, source="power")

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if event.distance % 2 == 0:
            old_distance = event.distance
            event.distance += 4

            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Even Steven Power to change {old_distance} to {event.distance}."
            )
        else:
            event.distance = 0

            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Even Steven Power and does not move on an odd roll."
            )

class FlipFlopPower(Power):
    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)

    def before_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        target = self.choose_target(game)
        if target is None:
            return

        if not self.should_use_flip(game, target):
            return

        event.cancelled = True
        old_position = target.position
        target.position = self.owner.position
        self.owner.position = old_position

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Flip Flop Power to switch with {target.name}."
        )

    def should_use_flip(self, game, target):
        # Avoid activating if it lets Scoocher immediately win.
        if game.would_power_activation_finish_scoocher():
            return False
        # If a roll could win it for me, do that because switching will never win it for me
        if self.owner.position + 6 >= game.track.length:
            return False

        # I don't want to trip when I land
        info = game.inspect_space(target.position, ignore_racer=self.owner)
        if info.has_trip:
            return False

        if info.has_bomb:
            return False

        # if the leaders could win, I swap
        if target.position + 6 >= game.track.length:
            return True

        # if the leaders are less than 6 away, we may do better with a dice roll
        if target.position < self.owner.position + 6:
            return False

        return True

    def choose_target(self, game):
        candidates = game.get_leaders()
        if not candidates:
            return None

        # *** Could check to see if anyone is on a point space
        return random.choice(candidates)

class GamblerPower(Power):
    MAX_SAVED = 5

    def __init__(self, owner):
        super().__init__(owner)
        self.saved_values = []
        self.scored_full_house = False
        self.scored_straight = False
        self.scored_five_kind = False

    def register(self, bus):
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return

        # Only save other racers' rolls.
        if event.racer is self.owner:
            return

        if not self.should_save_roll(event.value):
            return

        self.save_roll(event.value)

        self.log_power(game,f"{self.owner.name} uses Gambler Power to save {event.value}. "
            f"Saved values: {self.saved_values}."
        )

        self.try_score_hand(game, event)

    def hand_potential_score(self, values):
        counts = Counter(values)
        unique_values = set(values)

        score = 0

        # Five of a Kind potential
        if not self.scored_five_kind:
            most_common_count = max(counts.values(), default=0)
            score += 100 * most_common_count

        # Straight potential
        if not self.scored_straight:
            best_straight_overlap = max(
                len(unique_values & {1, 2, 3, 4, 5}),
                len(unique_values & {2, 3, 4, 5, 6})
            )
            score += 40 * best_straight_overlap

        # Full House potential
        if not self.scored_full_house:
            count_values = sorted(counts.values(), reverse=True)
            if len(count_values) >= 2:
                score += 30 * min(count_values[0], 3)
                score += 20 * min(count_values[1], 2)
            elif len(count_values) == 1:
                score += 30 * min(count_values[0], 3)

        return score

    def should_save_roll(self, value):
        # Always save until full.
        if len(self.saved_values) < self.MAX_SAVED:
            return True

        # If full, replace a value only if the new value improves the hand.
        current_score = self.hand_potential_score(self.saved_values)

        best_replacement_score = current_score
        for i in range(len(self.saved_values)):
            test_values = self.saved_values.copy()
            test_values[i] = value
            best_replacement_score = max(
                best_replacement_score,
                self.hand_potential_score(test_values)
            )

        return best_replacement_score > current_score

    def save_roll(self, value):
        if len(self.saved_values) < self.MAX_SAVED:
            self.saved_values.append(value)
            return

        # Replace the value that gives the best resulting hand.
        best_values = self.saved_values
        best_score = self.hand_potential_score(self.saved_values)

        for i in range(len(self.saved_values)):
            test_values = self.saved_values.copy()
            test_values[i] = value
            test_score = self.hand_potential_score(test_values)

            if test_score > best_score:
                best_score = test_score
                best_values = test_values

        self.saved_values = best_values

    def try_score_hand(self, game, event):
        if len(self.saved_values) < 5:
            return

        hand_type, bonus = self.best_scoring_hand()

        if hand_type is None:
            return

        if game.would_power_activation_finish_scoocher():
            return

        self.activate_power(
            game,
            event,
            f"{self.owner.name} scores {hand_type} with Gambler Power and moves {bonus}."
        )

        self.saved_values.clear()

        game.move_racer(self.owner, bonus, source="power")

    def best_scoring_hand(self):
        values = self.saved_values

        if not self.scored_five_kind and self.is_five_of_kind(values):
            self.scored_five_kind = True
            return "Five of a Kind", 4

        if not self.scored_straight and self.is_straight(values):
            self.scored_straight = True
            return "Straight", 2

        if not self.scored_full_house and self.is_full_house(values):
            self.scored_full_house = True
            return "Full House", 1

        return None, 0

    '''def best_possible_score(self, values):
        score = 0

        if not self.scored_five_kind and self.is_five_of_kind(values):
            score = max(score, 4)

        if not self.scored_straight and self.is_straight(values):
            score = max(score, 2)

        if not self.scored_full_house and self.is_full_house(values):
            score = max(score, 1)

        return score'''

    def is_five_of_kind(self, values):
        return len(values) == 5 and len(set(values)) == 1

    def is_straight(self, values):
        return sorted(values) in ([1, 2, 3, 4, 5], [2, 3, 4, 5, 6])

    def is_full_house(self, values):
        counts = sorted(Counter(values).values())
        return counts == [2, 3]

class GeniusPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.prediction = None

    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)
        bus.on(RollEvent, self.after_roll, priority=-40)

    def before_roll(self, game, event):
        if event.racer is not self.owner:
            return

        self.prediction = random.randint(1, 6)

        game.log.append(
            f"{self.owner.name} predicts they will roll {self.prediction}."
        )

    def after_roll(self, game, event):
        if event.racer is not self.owner:
            return

        if self.prediction is None:
            return

        if event.value == self.prediction:
            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Genius Power correctly and will take the next turn."
            )
            game.next_racer_override = self.owner

        self.prediction = None

class GunkPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main)

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is self.owner:
            return

        event.distance -= 1

        self.activate_power(
            game,
            event,
            f"{self.owner.name}'s Gunk Power reduces {event.racer.name}'s main move by 1."
        )

class HarePower(Power):
    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)
        bus.on(BeforeMainEvent, self.before_main)

    def before_roll(self, game, event):
        if self.inactive():
            return
        if event.racer.identifier == self.owner.identifier:
            leaders = game.get_leaders()
            if len(leaders) == 1:
                if leaders[0].identifier == self.owner.identifier:
                    event.cancelled = True
                    self.activate_power(
                        game,
                        event,
                        f"{event.racer.name} loses turn by Hare Power."
                    )

    def before_main(self, game, event: BeforeMainEvent):
        if self.inactive():
            return
        if event.racer.identifier == self.owner.identifier:
            original_distance = event.distance
            event.distance += 2

            self.activate_power(
                game,
                event,
                f"{event.racer.name} uses Hare Power to change {original_distance} to {event.distance}."
            )

class HecklerPower(Power):
    def register(self, bus):
        bus.on(EndTurnEvent, self.end_turn)

    def end_turn(self, game, event):
        if self.inactive():
            return
        if self.owner.finished or self.owner.eliminated:
            return

        if abs(event.end_position - event.start_position) <= 1:
            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Heckler Power because {event.racer.name} ended within 1 space of where they started."
            )
            game.move_racer(self.owner, 2, source="power")

class HighFivePower(Power):
    def register(self, bus):
        bus.on(AfterMoveEvent, self.after_move)

    def after_move(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if self.owner.position not in [5, 10, 15, 20, 25]:
            return

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses High Five Power and will take the next turn."
        )

        game.next_racer_override = self.owner

class HugeBabyPower(Power):
    def register(self, bus):
        bus.on(AfterMoveEvent, self.after_move, priority=-30)

    def after_move(self, game, event):
        if self.inactive():
            return
        baby = self.owner

        if baby.finished or baby.eliminated:
            return

        # Case 1: another racer stopped on Huge Baby
        if event.racer is not baby:
            if event.racer.position == baby.position:
                old_position = event.racer.position
                event.racer.position = max(0, baby.position - 1)

                self.activate_power(
                    game,
                    event,
                    f"{event.racer.name} cannot stop on {baby.name}'s space and is put from {old_position} to {event.racer.position}."
                )
            return

        # Case 2: Huge Baby stopped on other racers
        for other in game.racers:
            if other is baby or other.finished or other.eliminated:
                continue

            if other.position == baby.position:
                old_position = other.position
                other.position = max(0, baby.position - 1)

                self.activate_power(
                    game,
                    event,
                    f"{other.name} cannot be on {baby.name}'s space and is put from {old_position} to {other.position}."
                )

class HypnotistPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main, priority=-10)

    def before_main(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        # Don't give away points with the warp
        info = game.inspect_space(self.owner.position, ignore_racer=self.owner)
        if info.points > 0:
            return

        target = self.choose_target(game)
        if target is None:
            return

        old_position = target.position
        target.position = self.owner.position

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Hypnotist Power to warp {target.name} "
            f"from {old_position} to {self.owner.position}."
        )

    def choose_target(self, game):
        candidates = [
            racer for racer in game.racers
            if racer is not self.owner
            and not racer.finished
            and not racer.eliminated
            and racer.position > self.owner.position
        ]

        if not candidates:
            return None

        # Avoid activating if it lets Scoocher immediately win.
        if game.would_power_activation_finish_scoocher():
            return None

        # 1. Scoocher / Romantic ahead of me
        priority_targets = [
            racer for racer in candidates
            if racer.has_power(ScoocherPower)
               or racer.has_power(RomanticPower)
        ]

        if priority_targets:
            return max(priority_targets, key=lambda r: r.position)

        # 2. Pull the furthest-ahead racer
        return max(candidates, key=lambda r: r.position)

class InchwormPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll, priority=10)

    def after_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is self.owner:
            return

        if event.value != 1:
            return

        event.main_move_cancelled = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Inchworm Power. {event.racer.name}'s main move is skipped."
        )

        game.move_racer(self.owner, 1, source="power")

class LackeyPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is self.owner:
            return

        if event.value != 6:
            return

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Lackey Power because {event.racer.name} rolled a 6."
        )
        game.move_racer(self.owner, 2, source="power")

class LeaptoadPower(Power):
    def register(self, bus):
        bus.on(EnterSpaceEvent, self.enter_space)

    def enter_space(self, game, event):
        if self.inactive():
            return
        if event.racer.identifier != self.owner.identifier:
            return

        if not event.occupied:
            return

        skipped_positions = []
        next_position = event.new_position

        while game.is_space_occupied(next_position, ignore_racer=event.racer):
            skipped_positions.append(next_position)
            next_position += 1

        event.new_position = next_position

        for skipped_position in skipped_positions:
            self.activate_power(
                game,
                event,
                f"{event.racer.name} uses Leaptoad Power to skip occupied space {skipped_position}."
            )

class LegsPower(Power):
    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)

    def before_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if not self.should_use_legs(game):
            return

        distance = 5

        event.cancelled = True
        event.forced_main_distance = distance

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Legs Power to move {distance} instead of rolling."
        )

    def should_use_legs(self, game):
        if game.would_overshoot_with_stickler(self.owner, 5):
            return False

        finish = game.track.length

        # Always use it if it wins.
        if self.owner.position + 5 >= finish:
            return True

        # Don't activate if it lets Scoocher immediately finish.
        if game.would_power_activation_finish_scoocher():
            return False

        # If the 5th space is bad, don't do it
        landing_position = self.owner.position + 5

        info = game.inspect_space(landing_position, ignore_racer=self.owner)
        if info.has_trip:
            return False
        if info.arrow_move < 0:
            return False
        if info.has_bomb:
            return False

        return True

class LovableLoserPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main)

    def before_main(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if not self.is_alone_in_last_place(game):
            return

        self.owner.points += 1

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Lovable Loser Power and gains 1 point chip."
        )

    def is_alone_in_last_place(self, game):
        active = [
            racer for racer in game.get_active_racers()
            if not racer.finished
            and not racer.eliminated
        ]

        if not active:
            return False

        last_position = min(racer.position for racer in active)

        racers_in_last = [
            racer for racer in active
            if racer.position == last_position
        ]

        return len(racers_in_last) == 1 and racers_in_last[0] is self.owner

class MadBomberPower(Power):
    NUM_BOMBS = 3

    def register(self, bus):
        bus.on(BeforeRaceEvent, self.before_race)
        bus.on(BeforeMainEvent, self.before_main, priority=-20)
        bus.on(LandOnSpaceEvent, self.land_on_space, priority=-30)

    def before_race(self, game, event):
        #empty_spaces = [
        #    position for position in range(1, game.track.length)
        #    if not game.inspect_space(position).occupied
        #    and position not in game.bombs
        #]

        #if not empty_spaces:
        #    return

        #chosen_spaces = sorted(empty_spaces, reverse=True)[:self.NUM_BOMBS]
        chosen_spaces = [8, 20, 29]

        for position in chosen_spaces:
            game.bombs[position] = self.owner

        game.log.append(
            f"{self.owner.name} places bombs on spaces {chosen_spaces}."
        )

    def before_main(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if self.owner.position < 3:
            return

        if self.owner.position in game.bombs:
            return

        old_space = self.choose_bomb_to_move(game)
        if old_space is None:
            return

        if not self.should_move_bomb_to_self(game, old_space):
            return

        del game.bombs[old_space]
        game.bombs[self.owner.position] = self.owner

        self.activate_power(
            game,
            event,
            f"{self.owner.name} moves a bomb from space {old_space} to their space {self.owner.position}."
        )

    def land_on_space(self, game, event):
        if self.inactive():
            return

        bomb_owner = game.bombs.get(event.position)

        if bomb_owner is not self.owner:
            return

        del game.bombs[event.position]
        event.cancelled = True

        self.activate_power(
            game,
            event,
            f"{event.racer.name} lands on {self.owner.name}'s bomb at space {event.position} and moves back 3."
        )

        game.move_racer(event.racer, -3, source="power")

        # Reward the Mad Bomber.
        game.move_racer(self.owner, 2, source="power")

        game.log.append(
            f"{self.owner.name} advances 2 spaces because a bomb exploded."
        )

    def choose_bomb_to_move(self, game):
        bomb_spaces = self.get_my_bomb_spaces(game)

        risky_bombs = [
            space for space in bomb_spaces
            if 1 <= space - self.owner.position <= 6
        ]

        if risky_bombs:
            return min(risky_bombs)

        if not bomb_spaces:
            return None

        return min(bomb_spaces)

    def should_move_bomb_to_self(self, game, old_space):
        if game.would_power_activation_finish_scoocher():
            return False

        # Defensive: move a bomb I might hit this turn.
        if 1 <= old_space - self.owner.position <= 6:
            return True

        old_behind = len(game.get_racers_behind_position(old_space))
        new_behind = len(game.get_racers_behind_position(self.owner.position))

        return new_behind > old_behind

    def get_my_bomb_spaces(self, game):
        return [
            position for position, owner in game.bombs.items()
            if owner is self.owner
        ]

class MagicianPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll)

    def should_use_dicemonger_reroll(self, game, roll):
        # Magician already has better rerolls, so probably avoid Dicemonger.
        return False

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        original_roll = event.value
        current_roll = event.value
        rerolls_used = 0

        while rerolls_used < 2 and self.should_reroll(game, current_roll, rerolls_used):
            rerolls_used += 1
            current_roll = game.roll_die()

            game.log.append(
                f"{self.owner.name} uses Magician Power to reroll and gets {current_roll}."
            )

        if current_roll == original_roll:
            return

        event.value = current_roll

        self.activate_power(
            game,
            event,
            f"{self.owner.name}'s Magician Power changes {original_roll} to {current_roll}."
        )

    def should_reroll(self, game, current_roll, rerolls_used):
        spaces_left = game.track.length - self.owner.position

        # If this roll finishes, keep it.
        if current_roll >= spaces_left:
            if not game.exact_finish_required_for(self.owner):
                return False

            if current_roll == spaces_left:
                return False

        # With Stickler/exact-finish, avoid keeping an overshoot.
        if game.exact_finish_required_for(self.owner):
            if current_roll > spaces_left:
                return True

        # First roll: reroll 1-4.
        if rerolls_used == 0:
            return current_roll <= 4

        # Second roll: reroll 1-3.
        if rerolls_used == 1:
            return current_roll <= 3

        return False

class MOUTHPower(Power):
    def register(self, bus):
        bus.on(AfterMoveEvent, self.after_move, priority=-20 )

    def after_move(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if self.owner.finished or self.owner.eliminated:
            return

        others_on_space = [
            racer for racer in game.racers
            if racer is not self.owner
               and not racer.finished
               and not racer.eliminated
               and racer.position == self.owner.position
        ]

        if len(others_on_space) != 1:
            return

        victim = others_on_space[0]
        victim.eliminated = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses M.O.U.T.H. Power and eliminates {victim.name} from the race."
        )

class OddballPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if event.value % 2 == 0:
            return

        original = event.value
        event.value += 2

        self.activate_power(
            game,
            event,
            f"{self.owner.name}'s Oddball Power changes {original} to {event.value}."
        )

    def should_use_dicemonger_reroll(self, game, roll):
        modified_roll = roll + 2 if roll % 2 == 1 else roll

        spaces_left = game.track.length - self.owner.position

        if game.would_power_activation_finish_dicemonger():
            return False

        if game.would_power_activation_finish_scoocher():
            return False

        if modified_roll == spaces_left:
            return False

        if game.exact_finish_required_for(self.owner):
            if modified_roll > spaces_left:
                return True

        return modified_roll <= 4

class OddToddPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main, priority=-10)
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is self.owner:
            return

        if event.value % 2 == 1 and event.racer.has_power(EvenStevenPower):
            distance = 2 * event.value + 1

            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Odd Todd Power to move on {event.racer.name}'s odd roll."
            )
            game.move_racer(self.owner, distance, source="power")

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if event.distance % 2 == 1:
            old_distance = event.distance
            event.distance = 2 * event.distance + 1

            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Odd Todd Power to change {old_distance} to {event.distance}."
            )
        else:
            event.distance = 0

            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Odd Todd Power and does not move on an even roll."
            )

class PartyAnimalPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.pulled_this_turn = False

    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)
        bus.on(BeforeMainEvent, self.before_main)

    def before_roll(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        self.pulled_this_turn = False
        party_position = self.owner.position

        for other in game.racers:
            if other is self.owner or other.finished or other.eliminated:
                continue

            old_position = other.position

            if other.position < party_position:
                other.position += 1
            elif other.position > party_position:
                other.position -= 1

            if other.position != old_position:
                self.pulled_this_turn = True
                game.log.append(
                    f"{other.name} is pulled by {self.owner.name}'s Party Animal Power from {old_position} to {other.position}."
                )

        if self.pulled_this_turn:
            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Party Animal Power to pull racers closer."
            )

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        if getattr(event, "main_move_cancelled", False):
            return

        bonus = sum(
            1
            for other in game.racers
            if other is not self.owner
            and not other.finished
            and not other.eliminated
            and other.position == self.owner.position
        )

        if bonus <= 0:
            return

        old_distance = event.distance
        event.distance += bonus

        self.activate_power(
            game,
            event,
            f"{self.owner.name} gains +{bonus} to the main move from racers on its space."
        )

class PendulumPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main)

    def before_main(self, game, event):
        if self.inactive():
            return
        if event.racer is not self.owner:
            return

        ahead = 0
        behind = 0

        for racer in game.racers:
            if racer is self.owner:
                continue

            if racer.position > self.owner.position:
                ahead += 1
            elif racer.position < self.owner.position:
                behind += 1

        # modifier = (ahead // 2 - behind // 2)  # original power
        # modifier = (ahead - behind // 2) // 2  #less generous correction
        modifier = (ahead // 2 - behind // 4) #more generous correction

        if modifier == 0:
            return

        old_distance = event.distance
        event.distance += modifier

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Pendulum Power to change {old_distance} to {event.distance}."
        )

class PowerlessPower(Power):
    def register(self, bus):
        pass

class RocketScientistPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.using_power_this_turn = False

    def register(self, bus):
        bus.on(RollEvent, self.after_roll)
        bus.on(AfterMainEvent, self.after_main)

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if not self.should_use_power(game, event.value):
            self.using_power_this_turn = False
            return

        old_value = event.value
        event.value = 2 * old_value
        self.using_power_this_turn = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Rocket Scientist Power to change {old_value} to {event.value} and will trip."
        )

    def after_main(self, game, event):
        if event.racer is not self.owner:
            return

        if not self.using_power_this_turn:
            return

        self.using_power_this_turn = False
        game.trip_racer(self.owner, source="RocketScientistPower")

    def should_use_power(self, game, roll):
        finish = game.track.length

        if game.would_overshoot_with_stickler(self.owner, 2 * roll):
            return

        landing_position = self.owner.position + 2 * roll
        if landing_position >= finish:
            return True

        if game.would_power_activation_finish_scoocher():
            return False

        # If the landing_position is bad, don't do it
        info = game.inspect_space(landing_position, ignore_racer=self.owner)
        if info.has_trip:
            return False
        if info.arrow_move < 0:
            return False
        if info.has_bomb:
            return False

        return roll >= 4

class RomanticPower(Power):
    def register(self, bus):
        bus.on(AfterMoveEvent, self.after_move, priority=-5)

    def after_move(self, game, event):
        if self.inactive():
            return
        if self.owner.finished or self.owner.eliminated:
            return

        racers_on_space = game.racers_at_position(
            event.racer.position,
            exclude=event.racer
        )

        if len(racers_on_space) != 1:
            return

        state = (
            self.owner.position,
            tuple(
                (r.identifier, r.position, r.is_tripped, r.finished, r.eliminated)
                for r in game.racers
            )
        )

        if state in game.romantic_seen_states:
            game.log.append("Romantic loop detected; stopping Romantic chain.")
            return

        game.romantic_seen_states.add(state)

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Romantic Power because {event.racer.name} stopped with exactly one other racer."
        )

        game.move_racer(self.owner, 2, source="power")

class RubberBandPower(Power):
    MIN_GAIN = 4

    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)

    def before_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        target_position = self.choose_target_position(game)

        if target_position is None:
            return

        if game.would_power_activation_finish_scoocher():
            return

        old_position = self.owner.position
        self.owner.position = target_position
        event.cancelled = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Rubber Band Power to snap from {old_position} to {target_position}."
        )

    def choose_target_position(self, game):
        finish = game.track.length

        # If a normal roll could win, roll instead.
        if finish - self.owner.position <= 6:
            return None

        racers_ahead = [
            racer for racer in game.get_active_racers()
            if racer is not self.owner
            and racer.position > self.owner.position
        ]

        if not racers_ahead:
            return None

        nearest_ahead = min(racers_ahead, key=lambda r: r.position)

        target_position = nearest_ahead.position - 1

        if target_position <= self.owner.position:
            return None

        if target_position - self.owner.position < self.MIN_GAIN:
            return None

        info = game.inspect_space(target_position, ignore_racer=self.owner)

        if info.has_trip:
            return None
        if info.arrow_move < 0:
            return None
        if info.has_bomb:
            return None

        return target_position

class ScoocherPower(Power):
    def register(self, bus):
        bus.on(PowerActivatedEvent, self.power_activated)
        #bus.on(MovePreventedEvent, self.after_prevented_move)

    def after_prevented_move(self, game, event):
        if event.reason != "stickler":
            return
        if self.inactive():
            return

        self.log_power(
            game,
            f"{self.owner.name} uses Scoocher Power because Stickler stopped a move."
        )
        game.move_racer(self.owner, 1, source="power")


    def power_activated(self, game, event):
        #print("Scoocher heard:", event.owner.name, type(event.power).__name__)
        if self.inactive():
            return
        if event.owner is self.owner:
            return

        if self.owner.finished or self.owner.eliminated:
            return

        self.log_power(
            game,
            f"{self.owner.name} uses Scoocher Power because {event.owner.name}'s power happened."
        )
        game.move_racer(self.owner, 1, source="power")

class ScoocherPowerWeakened(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.used_this_turn = False

    def register(self, bus):
        bus.on(StartTurnEvent, self.start_turn)
        bus.on(PowerActivatedEvent, self.power_activated)

    def start_turn(self, game, event):
        if self.inactive():
            return
        self.used_this_turn = False

    def power_activated(self, game, event):
        if self.inactive():
            return
        if self.used_this_turn:
            return

        if event.owner is self.owner:
            return

        self.used_this_turn = True
        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Scoocher Power because {event.owner.name}'s power happened."
        )
        game.move_racer(self.owner, 1, source="power")

class SisyphusPower(Power):
    STARTING_POINTS = 4

    def register(self, bus):
        bus.on(BeforeRaceEvent, self.before_race)
        bus.on(RollEvent, self.after_roll)

    def before_race(self, game, event):
        if self.inactive():
            return

        self.owner.points += self.STARTING_POINTS

        game.log.append(f"{self.owner.name} uses Sisyphus Power and starts with {self.STARTING_POINTS} point chips.")

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if event.value != 6:
            return

        old_position = self.owner.position
        self.owner.position = 0
        event.main_move_cancelled = True

        if self.owner.points > 0:
            self.owner.points -= 1

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Sisyphus Power after rolling a 6, warps from {old_position} to Start, "
            f"loses 1 point chip, and skips their main move."
        )

class SixSevenPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.turns_taken = 0

    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)
        bus.on(AfterMainEvent, self.after_turn)

    def should_use_dicemonger_reroll(self, game, roll):
        if game. would_power_activation_finish_dicemonger():
            return False
        if game.would_power_activation_finish_scoocher():
            return False
        if self.turns_taken >= 6:
            return roll < 6
        return roll <= 3


    def after_turn(self, game, event):
        if event.racer is self.owner:
            self.turns_taken += 1

    def before_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if self.turns_taken < 6:
            return

        if not self.should_use_power(game):
            return

        event.cancelled = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Six Seven Power to move 6."
        )

        game.move_racer(self.owner, 6, source="power")

    def should_use_power(self, game):
        finish_distance = game.track.length - self.owner.position

        # If 6 finishes, take it.
        if finish_distance <= 6:
            return True

        info = game.inspect_space(
            self.owner.position + 6,
            ignore_racer=self.owner
        )

        # Avoid obvious disasters.
        if info.has_trip:
            return False
        if info.arrow_move < 0:
            return False
        if info.has_bomb:
            return False

        # Otherwise a guaranteed 6 beats rolling.
        return True

class SkipperPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll, priority=-30)

    def after_roll(self, game, event):
        if self.inactive():
            return
        if event.value != 1:
            return

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Skipper Power and will go next."
        )

        game.next_racer_override = self.owner

class SticklerPower(Power):
    @staticmethod
    def exact_finish_required(game, racer):
        return (
                racer is not None
                and not racer.finished
                and not racer.eliminated
                and not racer.has_power(SticklerPower)
                and game.get_active_stickler() is not None
        )

    def register(self, bus):
        pass

class SuckerfishPower(Power):
    MIN_RIDE_DISTANCE = 4

    def register(self, bus):
        bus.on(AfterMoveEvent, self.after_move)

    def after_move(self, game, event):
        if self.inactive():
            return

        if event.racer is self.owner:
            return

        # Suckerfish must have started on the mover's space.
        if self.owner.position != event.start_position:
            return

        distance = event.end_position - event.start_position

        # Don't ride backward.
        if distance <= 0:
            return

        if not self.should_take_ride(game, event, distance):
            return

        old_position = self.owner.position
        self.owner.position = event.end_position

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Suckerfish Power to ride with {event.racer.name} from {old_position} to {self.owner.position}."
        )

        game.mark_finished_if_needed(self.owner)

    def should_take_ride(self, game, event, distance):
        destination = event.end_position

        #Don't overshoot with stickler
        if game.would_overshoot_with_stickler(self.owner, distance):
            return False

        # Don't let Scoocher win
        if game.would_power_activation_finish_scoocher():
            return False

        # Finish the race if possible
        if destination >= game.track.length:
            return True

        # Don't ride with a BabaYaga. It will trip you.
        if event.racer.has_power(BabaYagaPower):
            return False

        info = game.inspect_space(destination, ignore_racer=self.owner)

        # Avoid obvious bad landings.
        if info.has_trip:
            return False
        if info.arrow_move < 0:
            return False
        if info.has_bomb:
            return False

        # Take strong rides.
        if distance >= self.MIN_RIDE_DISTANCE:
            return True

        # If no one else on my current space will move before me, take the small ride.
        if not self.better_ride_likely_before_my_turn(game):
            return True

        return False

    def better_ride_likely_before_my_turn(self, game):
        for racer in game.racers_before(self.owner):
            if racer is self.owner:
                continue

            if racer.finished or racer.eliminated:
                continue

            if racer.position == self.owner.position:
                return True

        return False

class ThirdWheelPower(Power):
    def register(self, bus):
        bus.on(BeforeMainEvent, self.before_main, priority=-20)

    def before_main(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if game.would_power_activation_finish_scoocher():
            return

        target = self.choose_target_space(game)
        if target is None:
            return

        old_position = self.owner.position
        info = game.inspect_space(target, ignore_racer=self.owner)

        self.owner.position = target

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Third Wheel Power to warp from space {old_position} "
            f"to space {target} with {info.racers[0].name} and {info.racers[1].name}."
        )

    def choose_target_space(self, game):
        candidates = []

        for position in range(self.owner.position + 1, game.track.length):
            info = game.inspect_space(position, ignore_racer=self.owner)

            if len(info.racers) != 2:
                continue

            if info.has_trip:
                continue
            if info.arrow_move < 0:
                continue
            if info.has_bomb:
                continue

            candidates.append(position)

        if not candidates:
            return None

        return max(candidates)

class TrackerPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.previous_roll = None
        self.previous_racer = None

    def register(self, bus):
        bus.on(RollEvent, self.after_roll)
        bus.on(BeforeRollEvent, self.before_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is self.owner:
            return

        self.previous_roll = event.value
        self.previous_racer = event.racer

    def before_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if self.previous_roll is None:
            return

        if not self.should_use_tracker(game, self.previous_roll):
            return

        event.cancelled = True
        event.forced_main_distance = self.previous_roll

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Tracker Power to move {self.previous_roll}, matching {self.previous_racer.name}'s roll."
        )

    def should_use_tracker(self, game, distance):
        if game.would_power_activation_finish_scoocher():
            return False

        if game.exact_finish_required_for(self.owner):
            if self.owner.position + distance > game.track.length:
                return False

        if self.owner.position + distance >= game.track.length:
                return True

        # If the landing_position is bad, don't do it
        info = game.inspect_space(self.owner.position + distance, ignore_racer=self.owner)
        if info.has_trip:
            return False
        if info.arrow_move < 0:
            return False
        if info.has_bomb:
            return False

        return distance >= 4

class TrafficCopPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.last_main_roll = None

    def register(self, bus):
        bus.on(RollEvent, self.after_roll)
        bus.on(AfterMainEvent, self.after_main)

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        self.last_main_roll = event.value

    def after_main(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if self.last_main_roll is None:
            return

        points = 7 - self.last_main_roll
        self.last_main_roll = None

        if points <= 0:
            return

        if game.would_power_activation_finish_scoocher():
            return

        planned_moves = self.plan_moves(game, points)

        if not planned_moves:
            return

        parts = []

        for entry in planned_moves.values():
            racer = entry["racer"]
            steps = entry["steps"]

            if steps == 0:
                continue

            direction_text = "forward" if steps > 0 else "back"
            parts.append(f"{racer.name} {direction_text} {abs(steps)}")

        if not parts:
            return

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Traffic Cop Power to move "
            + ", ".join(parts)
            + "."
        )

        for entry in planned_moves.values():
            racer = entry["racer"]
            steps = entry["steps"]

            if steps:
                game.move_racer(racer, steps, source="power")

    def plan_moves(self, game, points):
        planned_moves = {}

        for _ in range(points):
            action = self.choose_best_one_step_action(game, planned_moves)

            if action is None:
                break

            target, direction = action
            rid = target.identifier

            if rid not in planned_moves:
                planned_moves[rid] = {
                    "racer": target,
                    "steps": 0
                }

            planned_moves[rid]["steps"] += direction

        return planned_moves

    def choose_best_one_step_action(self, game, planned_moves):
        best_action = None
        best_score = 0

        for racer in game.get_active_racers():
            if racer is self.owner:
                continue

            # Forward action
            forward_score = self.score_one_step_action(
                game,
                racer,
                direction=1,
                planned_moves=planned_moves
            )

            if forward_score > best_score:
                best_score = forward_score
                best_action = (racer, 1)

            # Backward action
            backward_score = self.score_one_step_action(
                game,
                racer,
                direction=-1,
                planned_moves=planned_moves
            )

            if backward_score > best_score:
                best_score = backward_score
                best_action = (racer, -1)

        return best_action

    def score_one_step_action(self, game, racer, direction, planned_moves):
        current_offset = (
            planned_moves.get(racer.identifier, {})
            .get("steps", 0)
        )
        current_position = racer.position + current_offset
        new_position = current_position + direction

        if new_position < 0:
            return -9999

        if game.exact_finish_required_for(racer) and new_position > game.track.length:
            return -9999

        info = game.inspect_space(new_position, ignore_racer=racer)

        score = 0

        # Avoid helping another racer finish.
        if new_position >= game.track.length:
            if direction > 0:
                return -9999

        # Strongly move immediate threats backward.
        if direction < 0:
            spaces_left = game.track.length - current_position

            if 1 <= spaces_left <= 6:
                score += 100

            if game.has_danger_power(racer):
                score += 60

            if racer in game.get_leaders():
                score += 40

            score += max(0, current_position - self.owner.position)

        # Only move racers forward for specific tactical reasons.
        if direction > 0:
            if info.has_trip:
                score += 80

            if info.has_bomb:
                score += 60

            if info.arrow_move < 0:
                score += 60

            # Push far-behind racers forward a little to compress the field.
            if current_position < self.owner.position - 8:
                score += 10

            # Do not generally help leaders forward.
            if current_position >= self.owner.position:
                score -= 50

        # Avoid moving onto beneficial spaces.
        if info.arrow_move > 0:
            score -= 50

        # Avoid creating Huge Baby conflicts unless you want chaos.
        if any(r.has_power(HugeBabyPower) for r in info.racers):
            score -= 40

        return score

class TripleJumpPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.resolving_triple_jump = False

    def register(self, bus):
        bus.on(TripEvent, self.after_trip)

    def after_trip(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if self.resolving_triple_jump:
            return

        self.resolving_triple_jump = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Triple Jump Power and moves 3 more spaces."
        )

        game.move_racer(self.owner, 3, source="triple_jump")

        self.resolving_triple_jump = False

class UnderdogPower(Power):
    def __init__(self, owner):
        super().__init__(owner)
        self.my_last_roll = None
        self.waiting_for_next_roll = False

    def register(self, bus):
        bus.on(FinalRollEvent, self.after_final_roll)

    def after_final_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is self.owner:
            self.my_last_roll = event.value
            self.waiting_for_next_roll = True
            return

        if not self.waiting_for_next_roll:
            return

        self.waiting_for_next_roll = False

        if event.value > self.my_last_roll:
            self.activate_power(
                game,
                event,
                f"{self.owner.name} uses Underdog Power because {event.racer.name} rolled higher than {self.my_last_roll}."
            )
            game.move_racer(self.owner, 2, source="power")

class VirusPower(Power):
    def register(self, bus):
        bus.on(RollEvent, self.after_roll)

    def after_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if event.value not in [1, 2]:
            return

        for racer in game.get_active_racers():
            if racer is self.owner:
                continue

            racer.virus_skip_main_turn = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Virus Power. Each other racer will move 2 instead of taking their next main turn."
        )

class WranglerPower(Power):
    def register(self, bus):
        bus.on(BeforeRollEvent, self.before_roll)

    def before_roll(self, game, event):
        if self.inactive():
            return

        if event.racer is not self.owner:
            return

        if game.exact_finish_required_for(self.owner):
            if self.owner.position + 3 > game.track.length:
                return

        info = game.inspect_space(self.owner.position + 3, ignore_racer=self.owner)
        if info.has_trip:
            return
        if info.arrow_move < 0:
            return
        if info.has_bomb:
            return

        target = self.choose_trip_target(game)
        if target is None:
            return

        if game.would_power_activation_finish_scoocher():
            return

        event.cancelled = True

        self.activate_power(
            game,
            event,
            f"{self.owner.name} uses Wrangler Power to trip {target.name}."
        )

        game.trip_racer(target, source="WranglerPower")
        game.move_racer(self.owner, 3, source="power")

    def choose_trip_target(self, game):
        candidates = [
            racer for racer in game.get_active_racers()
            if racer is not self.owner
               and not racer.is_tripped
               and racer.position > self.owner.position
        ]

        if not candidates:
            return None

        priority = [
            racer for racer in candidates
            if racer.position >= game.track.length / 2
               and (
                       game.has_danger_power(racer)
                       or game.track.length - racer.position <= 6
               )
        ]

        if priority:
            return max(priority, key=lambda r: r.position)
