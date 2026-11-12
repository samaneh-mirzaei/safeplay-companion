from __future__ import annotations

from abc import ABC, abstractmethod
import time
import threading
import requests
import re
from html import unescape

from .models import Movie, Scene


class ProviderError(RuntimeError):
    pass


class GuideProvider(ABC):
    @abstractmethod
    def find(self, title: str, year: int | None = None) -> list[dict]: ...

    @abstractmethod
    def guide(self, item: dict) -> Movie: ...


def category_for(name: str) -> str | None:
    n = name.casefold()
    if any(x in n for x in ("sex", "nudity", "sexual")):
        return "sexual"
    if any(x in n for x in ("violence", "gore", "blood", "injury")):
        return "violence"
    if any(x in n for x in ("profanity", "language", "swear")):
        return "language"
    if any(x in n for x in ("drug", "alcohol", "substance", "smoking")):
        return "substances"
    return None


def hms(r: dict, prefix: str) -> float | None:
    values = [r.get(prefix + str(i)) for i in (1, 2, 3)]
    if any(x is None or isinstance(x, bool) or not isinstance(x, int) for x in values):
        return None
    h, m, s = values
    return h * 3600 + m * 60 + s if 0 <= h <= 24 and 0 <= m < 60 and 0 <= s < 60 else None


def normalize(item: dict, detail: dict, ratings: list[dict], topics: list[dict],
              categories: list[dict]) -> Movie:
    if not isinstance(item, dict) or not isinstance(detail, dict) or not isinstance(ratings, list):
        raise ProviderError("Unexpected API response schema")
    if item.get("itemTypeName", "").casefold() != "movie":
        raise ProviderError("Selected item is not a movie")
    item_id = item.get("id")
    if not isinstance(item_id, int) or not isinstance(item.get("name"), str):
        raise ProviderError("Movie ID or title is missing")
    cat_names = {c["id"]: c["name"] for c in categories
                 if isinstance(c, dict) and isinstance(c.get("id"), int) and isinstance(c.get("name"), str)}
    topic_map = {t["id"]: t for t in topics if isinstance(t, dict) and isinstance(t.get("id"), int)}
    scenes = []
    warnings = []
    for r in ratings:
        if not isinstance(r, dict) or r.get("yes") != 1 or r.get("itemId") != item_id:
            continue
        if not isinstance(r.get("id"), int):
            continue
        topic = topic_map.get(r.get("topicId"), {})
        names = [cat_names.get(topic.get(k), "") for k in ("topicCategoryId", "altTopicCategoryId")]
        mapped = {category_for(n) for n in names} - {None}
        if len(mapped) != 1:
            continue  # Ambiguous or unrelated topics require manual review.
        start, end = hms(r, "position"), hms(r, "safePosition")
        verified = r.get("isSceneAlert") is True
        scene = Scene(
            key=f"doesthedogdie:{r.get('id')}", start=start, end=end,
            category=mapped.pop(), source="doesthedogdie",
            reliability="verified" if verified and start is not None and end is not None and end > start else "community",
            topic=str(topic.get("name", "")), note=str(r.get("cueDescription") or ""),
            metadata={"rating_id": r.get("id"), "topic_id": r.get("topicId"),
                      "scene_alert": verified})
        if not scene.valid():
            scene.reliability = "unreliable"
            warnings.append(f"{scene.topic or scene.key}: missing or invalid interval")
        scenes.append(scene)
    if not scenes:
        warnings.append("No mapped scene intervals were returned; review guide topics manually.")
    elif not any(s.reliability == "verified" for s in scenes):
        warnings.append("Community timestamps require manual review and editing before they can skip.")
    return Movie(item["name"], item.get("releaseYear"), str(item_id), None,
                 "doesthedogdie", scenes, warnings)


class DoesTheDogDie(GuideProvider):
    BASE = "https://www.doesthedogdie.com/api/v3"
    _rate_lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, api_key: str, session=None):
        if not api_key.strip():
            raise ProviderError("Set a DoesTheDogDie API key in Settings or SAFEPLAY_DDD_API_KEY")
        self.session = session or requests.Session()
        self.session.headers.update({"X-API-KEY": api_key.strip(), "User-Agent": "SafePlay-Companion/0.1"})

    def _get(self, path: str, params=None):
        # Keep well below the Free tier's 30 requests/minute ceiling.
        try:
            with self._rate_lock:
                delay = 2.2 - (time.monotonic() - type(self)._last_request)
                if delay > 0:
                    time.sleep(delay)
                type(self)._last_request = time.monotonic()
            response = self.session.get(self.BASE + path, params=params, timeout=12)
            if response.status_code in (401, 403):
                raise ProviderError("API authentication or subscription does not permit this request")
            if response.status_code == 429:
                raise ProviderError("API rate limit reached; retry later")
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError(f"DoesTheDogDie request failed: {exc}") from exc

    def find(self, title: str, year: int | None = None) -> list[dict]:
        if not title or len(title) > 200:
            raise ProviderError("Enter a valid movie title")
        result = self._get("/items", {"name": title, **({"releaseYear": year} if year else {})})
        if not isinstance(result, list):
            raise ProviderError("Unexpected movie search response")
        return [x for x in result if isinstance(x, dict) and x.get("itemTypeName", "").casefold() == "movie"]

    def guide(self, item: dict) -> Movie:
        item_id = item.get("id")
        if not isinstance(item_id, int) or item_id < 1:
            raise ProviderError("Invalid movie ID")
        detail = self._get(f"/items/{item_id}")
        ratings = self._get(f"/items/{item_id}/ratings")
        topics = self._get("/topics")
        categories = self._get("/topiccategories")
        return normalize(item, detail, ratings, topics, categories)


class CleanStream:
    """Read the public, community-contributed VideoSkip seed catalog."""
    URL = "https://raw.githubusercontent.com/ameen-roayan/stremio-cleanstream/main/data/seed-data.json"
    CATEGORY = {"nudity": "sexual", "sex": "sexual", "violence": "violence",
                "language": "language", "drugs": "substances"}

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def scenes(self, title: str, year: int | None) -> list[Scene]:
        try:
            response = self.session.get(self.URL, timeout=20)
            response.raise_for_status()
            catalog = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError(f"CleanStream catalog unavailable: {exc}") from exc
        if not isinstance(catalog, list):
            raise ProviderError("Unexpected CleanStream catalog format")
        normal = lambda value: re.sub(r"[^a-z0-9]+", "", str(value).casefold())
        matches = [item for item in catalog if isinstance(item, dict)
                   and normal(item.get("title", "")) == normal(title)
                   and (year is None or item.get("year") == year)
                   and item.get("type") == "movie"]
        if len(matches) != 1:
            return []  # Never guess between editions or similarly named titles.
        result = []
        for segment in matches[0].get("segments", []):
            if not isinstance(segment, dict):
                continue
            category = self.CATEGORY.get(segment.get("category"))
            start, end = segment.get("startMs"), segment.get("endMs")
            if category is None or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (start, end)):
                continue
            scene = Scene(key="cleanstream:" + str(segment.get("id", len(result))),
                          start=start / 1000, end=end / 1000, category=category,
                          source="CleanStream / VideoSkip", reliability="provided",
                          topic=str(segment.get("subcategory") or segment.get("category") or ""),
                          note=str(segment.get("comment") or ""),
                          metadata={"imdb_id": matches[0].get("imdbId"),
                                    "channel": segment.get("channel"),
                                    "verified": bool(segment.get("verified"))})
            if scene.valid():
                result.append(scene)
        return result


class CringeMDb:
    """Read public scene intervals from a movie's scene-by-scene guide."""
    BASE = "https://cringemdb.com/movie/"

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def scenes(self, title: str, year: int | None) -> list[Scene]:
        if not year:
            return []
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
        url = f"{self.BASE}{slug}-{year}"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 404:
                return []
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderError(f"CringeMDb guide unavailable: {exc}") from exc
        page = response.text
        if "sg-scene" not in page:
            return []
        runtime_match = re.search(r"Times added by CringeMDb are from a subtitle for the\s+(\d+)h\s+(\d+)m release", page)
        reference_runtime = (int(runtime_match.group(1)) * 3600 + int(runtime_match.group(2)) * 60
                             if runtime_match else None)
        result = []
        for match in re.finditer(r'<article\s+class="sg-scene"\s+id="scene-(\d+)"[^>]*>(.*?)</article>',
                                 page, re.S):
            body = match.group(2)
            times = re.search(r'<div class="sg-time">\s*<strong>([\d:]+)</strong>\s*<span>to\s+([\d:]+)</span>', body)
            heading = re.search(r'<h3>\s*<i class="sg-dot\s+([^"]+)"', body)
            if not times or not heading:
                continue
            category_name = heading.group(1).casefold()
            category = ("sexual" if "sex" in category_name or "nudity" in category_name or "suggest" in category_name
                        else "violence" if "violence" in category_name
                        else "language" if "language" in category_name
                        else "substances" if "drug" in category_name or "alcohol" in category_name else None)
            if not category:
                continue
            def seconds(value):
                parts = [int(p) for p in value.split(":")]
                return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
            note = re.search(r'<div class="sg-body">.*?<p>(.*?)</p>', body, re.S)
            scene = Scene(key="cringemdb:" + match.group(1),
                          start=seconds(times.group(1)), end=seconds(times.group(2)),
                          category=category, source="CringeMDb", reliability="provided",
                          topic=category_name,
                          note=unescape(re.sub(r"<[^>]+>", "", note.group(1)).strip()) if note else "",
                          metadata={"url": url, "unverified": "Unverified" in body,
                                    "reference_runtime": reference_runtime})
            if scene.valid():
                result.append(scene)
        return result


def fallback_providers(scenes: list[Scene]):
    """Query unused sources only when the primary guide has gaps."""
    if scenes and all(scene.valid() for scene in scenes):
        return []
    sources = {scene.source for scene in scenes}
    return [provider for name, provider in (("CleanStream / VideoSkip", CleanStream),
                                             ("CringeMDb", CringeMDb)) if name not in sources]
