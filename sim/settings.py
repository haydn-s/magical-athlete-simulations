"""
Power settings a run can override, for tuning designs without editing Powers.py.

A setting is a class attribute on a power, by convention in capitals:

    class SisyphusPower(Power):
        STARTING_POINTS = 4

Override it for one run with `python -m sim run --set Sisyphus.STARTING_POINTS=3`,
or try several values with `python -m sim sweep --set Sisyphus.STARTING_POINTS=2..6`.
Name the power by its class (SisyphusPower) or by a racer that has it (Sisyphus).

To make a number tunable, move it into a class attribute and read it as
self.NAME inside the power. `python -m sim sweep --list` shows every setting.
"""
import contextlib
import difflib
import threading

import Powers

from sim import roster

MAX_VALUES = 50
_MISSING = object()
# Overrides change class attributes for the whole process, so in-process users
# (replays, single-process runs) take turns.
_lock = threading.RLock()


class SettingError(ValueError):
    """A --set that can't be applied, with a message saying why."""


def power_classes():
    return {
        name: cls
        for name, cls in vars(Powers).items()
        if isinstance(cls, type) and issubclass(cls, Powers.Power) and cls is not Powers.Power
    }


def _is_setting(name, value):
    return name.isupper() and not name.startswith("_") and isinstance(value, (bool, int, float, str))


def settings_of(cls):
    """{name: current value} for a power class, including inherited settings."""
    found = {}
    for klass in reversed(cls.__mro__):
        found.update({k: v for k, v in vars(klass).items() if _is_setting(k, v)})
    return found


def racers_with(class_name):
    """Default-pool racers (or, failing that, any registered racer) whose power is this class."""
    cls = power_classes()[class_name]
    matches = [e for e in roster.ROSTER.values() if any(isinstance(p, cls) for p in e.make().powers)]
    standard = [e.name for e in matches if e.in_default_pool]
    return standard or [e.name for e in matches]


def tunables():
    """Every setting: [(power class, setting, current value, racers that have it)], sorted."""
    rows = []
    for name, cls in sorted(power_classes().items()):
        for setting, value in sorted(vars(cls).items()):
            if _is_setting(setting, value):
                rows.append((name, setting, value, racers_with(name)))
    return rows


def resolve_power(target):
    """(power class name, racer name or None) for a power class or racer name."""
    classes = power_classes()
    if target in classes:
        return target, None
    try:
        entry = roster.lookup(target)
    except KeyError:
        close = difflib.get_close_matches(target, list(classes) + list(roster.ROSTER), n=3)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise SettingError(f"Unknown power or racer {target!r}.{hint}") from None
    powers = entry.make().powers
    if not powers:
        raise SettingError(f"{entry.name} has no power to change.")
    return type(powers[0]).__name__, entry.name


def _convert(text, kind, where):
    text = text.strip()
    if kind is bool:
        lowered = text.lower()
        if lowered in ("true", "yes", "1"):
            return True
        if lowered in ("false", "no", "0"):
            return False
        raise SettingError(f"{where}: {text!r} isn't true or false.")
    if kind is int:
        try:
            return int(text)
        except ValueError:
            raise SettingError(f"{where}: {text!r} isn't a whole number.") from None
    if kind is float:
        try:
            return float(text)
        except ValueError:
            raise SettingError(f"{where}: {text!r} isn't a number.") from None
    return text


def parse_values(text, current, where):
    """
    Values for a setting, typed like its current value. Accepts lists and ranges:
    "3", "2,4,6", "2..6", "0..20:5" (every 5), "0.5..1.5:0.25", "true,false".
    """
    kind = type(current)
    values = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if ".." in part and kind in (int, float):
            span, _, step_text = part.partition(":")
            start_text, _, stop_text = span.partition("..")
            start = _convert(start_text, kind, where)
            stop = _convert(stop_text, kind, where)
            step = _convert(step_text, kind, where) if step_text else 1
            if step <= 0:
                raise SettingError(f"{where}: the step in {part!r} must be positive.")
            if stop < start:
                raise SettingError(f"{where}: {part!r} runs backwards.")
            count = int(round((stop - start) / step)) + 1
            if count > MAX_VALUES:
                raise SettingError(f"{where}: {part!r} has {count} values; the limit is {MAX_VALUES}.")
            values += [start + i * step if kind is int else round(start + i * step, 10) for i in range(count)]
        else:
            values.append(_convert(part, kind, where))
    unique = list(dict.fromkeys(values))
    if not unique:
        raise SettingError(f"{where}: give at least one value.")
    if len(unique) > MAX_VALUES:
        raise SettingError(f"{where}: {len(unique)} values is more than the limit of {MAX_VALUES}.")
    return unique


def parse_assignment(text):
    """
    "Sisyphus.STARTING_POINTS=2..6" -> (power class, setting, [values], racer or None).
    """
    name, eq, value_text = text.partition("=")
    target, dot, setting = name.strip().rpartition(".")
    if not eq or not dot or not target or not setting:
        raise SettingError(f"{text!r}: write settings as Racer.SETTING=value, e.g. Sisyphus.STARTING_POINTS=3.")
    class_name, racer = resolve_power(target)
    available = settings_of(power_classes()[class_name])
    if setting not in available:
        close = difflib.get_close_matches(setting, available, n=3)
        if close:
            hint = f" Did you mean: {', '.join(close)}?"
        elif available:
            hint = f" It has: {', '.join(sorted(available))}."
        else:
            hint = " It has no settings yet; see `python -m sim sweep --list`."
        raise SettingError(f"{class_name} has no setting {setting!r}.{hint}")
    values = parse_values(value_text, available[setting], f"{class_name}.{setting}")
    return class_name, setting, values, racer


def check_override(class_name, setting, value):
    """Validate one (power class, setting, value) from a saved run or a job request."""
    classes = power_classes()
    if class_name not in classes:
        raise SettingError(f"Unknown power {class_name!r}.")
    available = settings_of(classes[class_name])
    if setting not in available:
        raise SettingError(f"{class_name} has no setting {setting!r}.")
    current = available[setting]
    if isinstance(current, bool) != isinstance(value, bool):
        raise SettingError(f"{class_name}.{setting} must be {'true or false' if isinstance(current, bool) else 'a number'}.")
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        if not isinstance(value, (int, float)) or (isinstance(current, int) and isinstance(value, float) and not value.is_integer()):
            raise SettingError(f"{class_name}.{setting} must be a {'whole number' if isinstance(current, int) else 'number'}.")
        value = type(current)(value)
    if isinstance(current, str) and not isinstance(value, str):
        raise SettingError(f"{class_name}.{setting} must be text.")
    return class_name, setting, value


def describe(overrides):
    return ", ".join(f"{cls}.{setting}={value}" for cls, setting, value in overrides)


@contextlib.contextmanager
def applied(overrides, exclusive=False):
    """
    Apply (power class, setting, value) overrides for the duration of the block.
    exclusive=True takes the lock even with no overrides, for code that must not
    see another thread's overrides (replays in the server).
    """
    if not overrides:
        if exclusive:
            with _lock:
                yield
        else:
            yield
        return
    classes = power_classes()
    with _lock:
        saved = []
        try:
            for class_name, setting, value in overrides:
                cls = classes[class_name]
                saved.append((cls, setting, cls.__dict__.get(setting, _MISSING)))
                setattr(cls, setting, value)
            yield
        finally:
            for cls, setting, previous in reversed(saved):
                if previous is _MISSING:
                    delattr(cls, setting)
                else:
                    setattr(cls, setting, previous)
