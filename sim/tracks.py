"""
Track layouts available to the simulator.

Note: several powers hard-code positions for a 30-space track (Crossing Guard's
crosswalk at 27, Mad Bomber's bombs at 8/20/29, High Five's multiples of 5,
Blimp's halfway point at 15). Tracks of other lengths will run, but those
racers won't behave as designed on them.
"""
from Basics import Track, TrackSpace

MILD_MILE = Track(name="Mild Mile", length=30, spaces={})

WILD_WILDS = Track(name="Wild Wilds", length=30,
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

TRACKS = {
    "mild": MILD_MILE,
    "wild": WILD_WILDS,
}


def lookup(key):
    try:
        return TRACKS[key.lower()]
    except KeyError:
        raise KeyError(f"Unknown track {key!r}. Known tracks: {', '.join(TRACKS)}") from None
