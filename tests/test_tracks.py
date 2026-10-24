"""Tests for track files (sim/tracks.py) and the powers that depend on track layout."""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Basics import Game, Track, TrackSpace
from Events import AfterMoveEvent, BeforeMainEvent, BeforeRaceEvent, MoveEvent
from Powers import BlimpPower, CrossingGuardPower, HighFivePower, MadBomberPower
from Racers import Blimp, CrossingGuard, HighFive, MadBomber
from sim import batch, tracks
from sim.replay import record_game
from sim.tracks import TrackError, track_from_spec


def spec(**overrides):
    base = {"name": "Test Track", "length": 40, "spaces": {"5": {"trip": True}, "9": {"move": 2}, "12": {"points": 1}}}
    base.update(overrides)
    return base


class TrackFileTest(unittest.TestCase):
    def test_builds_a_track(self):
        track = track_from_spec(spec())
        self.assertEqual((track.name, track.length), ("Test Track", 40))
        self.assertEqual(track.spaces[9], TrackSpace(move=2))
        self.assertEqual(track_from_spec(tracks.track_to_json(track)), track)  # round-trips through the API form

    def test_standard_tracks_match_the_originals(self):
        self.assertEqual(tracks.WILD_WILDS, Track(name="Wild Wilds", length=30, spaces={
            1: TrackSpace(points=1), 5: TrackSpace(trip=True), 7: TrackSpace(move=3), 11: TrackSpace(move=1),
            13: TrackSpace(points=1), 16: TrackSpace(move=-4), 17: TrackSpace(trip=True), 23: TrackSpace(move=2),
            24: TrackSpace(move=-2), 26: TrackSpace(trip=True),
        }))
        self.assertEqual(tracks.MILD_MILE, Track(name="Mild Mile", length=30, spaces={}))

    def test_explains_mistakes(self):
        cases = [
            ("length must be a whole number from 10 to 200", spec(length=5)),
            ("name must be text", spec(name="")),
            ("unknown field 'lenght'", {**spec(), "lenght": 3}),
            ("space numbers run from 1 to 39", spec(spaces={"40": {"trip": True}})),
            ("space numbers run from 1 to 39", spec(spaces={"0": {"trip": True}})),
            ("unknown effect 'jump'", spec(spaces={"3": {"jump": 2}})),
            ("has no effect", spec(spaces={"3": {}})),
            ("would leave the track", spec(spaces={"2": {"move": -3}})),
            ("trip must be true or false", spec(spaces={"3": {"trip": "yes"}})),
            ("move must be a whole number", spec(spaces={"3": {"move": 1.5}})),
        ]
        for message, bad in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(TrackError, message):
                    track_from_spec(bad)

    def test_scans_a_folder_and_reports_broken_files(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, content in {
                "ok.json": json.dumps(spec()),
                "broken.json": "{not json",
                "Bad Name.json": json.dumps(spec()),
                "notes.txt": "ignored",
            }.items():
                with open(os.path.join(folder, name), "w") as f:
                    f.write(content)
            found, errors = tracks.scan(folder)
        self.assertEqual(list(found), ["ok"])
        self.assertIn("not valid JSON", errors["broken"])
        self.assertIn("rename it", errors["Bad Name"])

    def test_races_a_file_by_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "Sprint.json")
            with open(path, "w") as f:
                json.dump(spec(), f)
            config, _ = batch.build_config(games=50, seed=1, track=path)
            self.assertEqual(config.track.length, 40)
            self.assertEqual(tracks.track_key(path), "sprint")
            summary, _ = batch.execute(config, track_key=path, workers=1)
        self.assertEqual(summary["manifest"]["config"]["track"], "sprint")
        self.assertEqual(summary["manifest"]["config"]["track_spec"]["length"], 40)

    def test_runs_replay_from_their_recorded_layout(self):
        config, _ = batch.build_config(games=20, seed=2, track="wild")
        data = batch.config_to_json(config, "wild", [])
        data["track"] = "a-track-that-was-deleted"
        rebuilt = batch.config_from_json(data)
        self.assertEqual(rebuilt.track, tracks.WILD_WILDS)
        self.assertEqual(record_game(rebuilt, 3)["results"], record_game(config, 3)["results"])


def game_on(length, racers, spaces=None):
    game = Game(racers=racers, track=Track("Custom", length, spaces or {}), rng=random.Random(1))
    game.emit(BeforeRaceEvent())
    return game


class TrackAwarePowersTest(unittest.TestCase):
    def test_crossing_guard_sits_three_before_the_finish(self):
        guard = CrossingGuard("CrossingGuard", 1)
        game_on(40, [guard])
        self.assertEqual(guard.get_power(CrossingGuardPower).crosswalk_position, 37)

        guard = CrossingGuard("CrossingGuard", 1)
        game_on(40, [guard], {37: TrackSpace(trip=True), 36: TrackSpace(move=1)})
        self.assertEqual(guard.get_power(CrossingGuardPower).crosswalk_position, 35)  # nearest unmarked before

    def test_mad_bomber_scales_its_bombs(self):
        bomber = MadBomber("MadBomber", 1)
        game = game_on(60, [bomber])
        self.assertEqual(sorted(game.bombs), [16, 40, 59])

        bomber = MadBomber("MadBomber", 1)
        game = game_on(60, [bomber], {16: TrackSpace(trip=True)})
        self.assertEqual(sorted(game.bombs), [17, 40, 59])  # moved off the trip space

    def test_high_five_counts_every_multiple_of_five(self):
        racer = HighFive("HighFive", 1)
        game = game_on(40, [racer])
        power = racer.get_power(HighFivePower)
        for position, fires in ((35, True), (40, False), (33, False), (0, False)):
            with self.subTest(position=position):
                racer.position = position
                game.next_racer_override = None
                power.after_move(game, AfterMoveEvent(racer=racer, start_position=0, end_position=position,
                                                      move=MoveEvent(racer=racer, steps_remaining=0)))
                self.assertEqual(game.next_racer_override is racer, fires)

    def test_blimp_switches_at_the_halfway_point(self):
        racer = Blimp("Blimp", 1)
        game = game_on(40, [racer])
        power = racer.get_power(BlimpPower)
        for position, expected in ((19, 6), (20, 2)):
            with self.subTest(position=position):
                racer.position = position
                event = BeforeMainEvent(racer=racer, distance=3)
                power.before_main(game, event)
                self.assertEqual(event.distance, expected)


if __name__ == "__main__":
    unittest.main()
