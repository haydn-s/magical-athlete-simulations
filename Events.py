#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 11:00:36 2026

@author: kaltmann
"""
from collections import defaultdict
from typing import Callable, DefaultDict, Type
from dataclasses import dataclass

class Event:
    """
    Base class for all events.
    Specific events should inherit from this.
    """
    cancelled: bool = False


class EventBus:
    def __init__(self):
        self.listeners: DefaultDict[Type[Event], list] = defaultdict(list)

    # Events.py

    def on(self, event_type, callback, priority=0):
        self.listeners[event_type].append((priority, callback))
        self.listeners[event_type].sort(key=lambda item: item[0])
        #print(
        #    "REGISTER",
        #    "bus", id(self),
        #    "listeners", id(self.listeners),
        #    "event_type", event_type,
        #    "event_type_id", id(event_type),
        #    "len", len(self.listeners[event_type])
        #)

    def emit(self, game, event):
        event_type = type(event)

        #print("About to emit", event_type)

        for priority, callback in self.listeners[event_type]:
            #print("CALLING", callback)
            callback(game, event)

        #print("Finished emit")



@dataclass
class StartTurnEvent(Event):
    racer: "Racer"
    cancelled: bool = False


@dataclass
class BeforeRollEvent(Event):
    racer: "Racer"
    value: int = 0
    cancelled: bool = False
    forced_main_distance: int | None = None
    
@dataclass
class RollEvent(Event):
    racer: "Racer"
    value: int
    main_move_cancelled: bool = False
    cancelled: bool = False
    tripped: bool = False

@dataclass
class BeforeMainEvent(Event):
    racer: "Racer"
    distance: int
    tripped: bool = False
    cancelled: bool = False

@dataclass
class AfterMainEvent(Event):
    racer: "Racer"
    start_position: int
    end_position: int
    distance: int
    tripped: bool = False
    cancelled: bool = False

@dataclass
class MoveEvent(Event):
    racer: "Racer"
    steps_remaining: int
    direction: int = 1
    source: str = "main"
    tripped: bool = False
    cancelled: bool = False

@dataclass
class AfterMoveEvent(Event):
    racer: "Racer"
    start_position: int
    end_position: int
    move: MoveEvent
    tripped: bool = False
    cancelled: bool = False

@dataclass
class EnterSpaceEvent(Event):
    racer: "Racer"
    old_position: int
    new_position: int
    move: MoveEvent
    occupied: bool = False
    cancelled: bool = False


@dataclass
class PassRacerEvent(Event):
    mover: "Racer"
    passed: "Racer"
    position: int
    move: MoveEvent
    cancelled: bool = False


@dataclass
class EndTurnEvent(Event):
    racer: "Racer"
    start_position: int
    end_position: int
    recovered_from_trip: bool = False
    cancelled: bool = False

@dataclass
class PowerActivatedEvent(Event):
    owner: "Racer"
    power: object
    source_event: Event
    cancelled: bool = False

@dataclass
class BeforeRaceEvent(Event):
    pass

@dataclass
class TripEvent(Event):
    racer: "Racer"
    source: str = ""
    cancelled: bool = False

@dataclass
class MovePreventedEvent(Event):
    racer: "Racer"
    attempted_distance: int
    reason: str

@dataclass
class LandOnSpaceEvent(Event):
    racer: "Racer"
    position: int

@dataclass
class DicemongerRerollEvent(Event):
    racer: "Racer"
    old_value: int
    new_value: int

@dataclass
class FinalRollEvent(Event):
    racer: "Racer"
    value: int