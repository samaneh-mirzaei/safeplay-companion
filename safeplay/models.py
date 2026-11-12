from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import re

CATEGORIES = {
    "sexual": "Sexual Content & Nudity",
    "violence": "Violence & Gore",
    "language": "Profanity & Language",
    "substances": "Drugs & Alcohol",
}


@dataclass
class Scene:
    key: str
    start: float | None
    end: float | None
    category: str
    source: str
    reliability: str = "community"
    enabled: bool = True
    topic: str = ""
    note: str = ""
    manual: bool = False
    metadata: dict = field(default_factory=dict)

    def valid(self, duration: float | None = None) -> bool:
        if self.category not in CATEGORIES or self.start is None or self.end is None:
            return False
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (self.start, self.end)):
            return False
        return 0 <= self.start < self.end and (duration is None or self.end <= duration + 2)

    def can_skip(self, duration: float | None, confirmed: bool) -> bool:
        reference = self.metadata.get("reference_runtime")
        if reference and duration is not None and abs(duration - reference) > 120:
            return False
        return (self.enabled and confirmed and duration is not None and self.valid(duration)
                and self.reliability in {"verified", "manual", "provided"})


@dataclass
class Movie:
    title: str
    year: int | None = None
    external_id: str = ""
    runtime: float | None = None
    source: str = "doesthedogdie"
    scenes: list[Scene] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def identify_file(path: str) -> tuple[str, int | None]:
    name = Path(path).stem
    found = re.search(r"(?:^|[. _([{])((?:19|20)\d{2})(?=$|[. _)}\]])", name)
    year = int(found.group(1)) if found else None
    if found:
        name = name[:found.start()]
    name = re.sub(r"[._]+", " ", name)
    name = re.split(r"\b(?:1080p|2160p|720p|bluray|webrip|web-dl|x264|x265)\b", name, flags=re.I)[0]
    return re.sub(r"\s+", " ", name).strip(" -[]()"), year


def runtime_warning(player: float | None, guide: float | None) -> str | None:
    if not player or not guide:
        return "Guide runtime is unavailable; confirm this movie edition before skipping."
    difference = abs(player - guide)
    if difference > max(120, guide * 0.02):
        return f"Runtime differs by {difference / 60:.1f} minutes; confirm the edition and timestamps."
    return None
