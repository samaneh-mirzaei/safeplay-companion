from __future__ import annotations

import time
from .models import Scene


class SkipEngine:
    def __init__(self, margin: float = 0.5):
        self.margin = margin
        self.scenes: list[Scene] = []
        self.filters: dict[str, bool] = {}
        self.confirmed = False
        self.enabled = False
        self.duration: float | None = None
        self.fired: set[str] = set()
        self.last_position: float | None = None
        self.pending_target: float | None = None
        self.pending_at = 0.0
        self.suspended = False

    def load(self, scenes: list[Scene], duration: float | None, confirmed=False):
        self.scenes = scenes
        self.duration = duration
        self.confirmed = confirmed
        self.fired.clear()
        self.last_position = None
        self.pending_target = None
        self.suspended = False

    def tick(self, position: float | None, paused: bool, now: float | None = None):
        if now is None:
            now = time.monotonic()
        if position is None or position < 0:
            return None
        if self.pending_target is not None:
            if abs(position - self.pending_target) <= 2:
                self.pending_target = None
            elif now - self.pending_at < 3:
                if position < self.pending_target - 3 and now - self.pending_at > 1:
                    self.suspended = True  # likely a Syncplay correction
                return None
            else:
                self.pending_target = None
        if self.last_position is not None and position < self.last_position - 3:
            # A deliberate backward seek makes earlier scenes eligible again.
            self.fired = {s.key for s in self.scenes if s.start is not None and s.start < position - 1}
        self.last_position = position
        if paused or not self.enabled or self.suspended or not self.confirmed:
            return None
        usable = sorted((s for s in self.scenes if s.can_skip(self.duration, True)
                         and self.filters.get(s.category, False)), key=lambda s: s.start)
        matching = [s for s in usable if s.key not in self.fired
                    and s.start - self.margin <= position < s.end]
        if not matching:
            return None
        initial = matching[0]
        end = initial.end
        included = {initial.key}
        changed = True
        while changed:
            changed = False
            for s in usable:
                if s.key not in included and s.start <= end + self.margin and s.end > end:
                    included.add(s.key)
                    end = s.end
                    changed = True
        target = min(end + self.margin, self.duration or end + self.margin)
        if target <= position + 0.2:
            return None
        self.fired.update(included)
        self.pending_target, self.pending_at = target, now
        return target, sorted(included)

    def seek_failed(self, keys: list[str]):
        self.fired.difference_update(keys)
        self.pending_target = None

    def resume_after_conflict(self):
        self.suspended = False
        self.pending_target = None
