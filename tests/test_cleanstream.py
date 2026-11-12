from safeplay.provider import CleanStream, CringeMDb, fallback_providers
from safeplay.models import Scene


class Response:
    def raise_for_status(self):
        pass

    def json(self):
        return [{"imdbId": "tt1234567", "title": "Example Movie", "year": 2020,
                 "type": "movie", "segments": [
                     {"id": "one", "startMs": 120000, "endMs": 125000,
                      "category": "violence", "channel": "both"},
                     {"id": "bad", "startMs": 130000, "endMs": 120000,
                      "category": "violence"}]}]


class Session:
    def get(self, url, timeout):
        assert "seed-data.json" in url
        return Response()


def test_timestamped_scene_can_skip_after_edition_confirmation():
    scenes = CleanStream(Session()).scenes("Example Movie", 2020)
    assert len(scenes) == 1
    assert (scenes[0].start, scenes[0].end) == (120, 125)
    assert not scenes[0].can_skip(200, False)
    assert scenes[0].can_skip(200, True)


def test_does_not_guess_wrong_year():
    assert CleanStream(Session()).scenes("Example Movie", 2021) == []


def test_cringemdb_scene_and_runtime_guard():
    class Page:
        status_code = 200
        text = ('Times added by CringeMDb are from a subtitle for the 1h 51m release'
                '<article class="sg-scene" id="scene-4">'
                '<div class="sg-time"><strong>01:02</strong><span>to 01:05</span></div>'
                '<div class="sg-body"><h3><i class="sg-dot violence"></i>Violence</h3>'
                '<p>A short scene.</p><span>Unverified</span></div></article>')

        def raise_for_status(self):
            pass

    class Client:
        def get(self, url, timeout):
            assert url.endswith("example-movie-2020")
            return Page()

    scenes = CringeMDb(Client()).scenes("Example Movie", 2020)
    assert len(scenes) == 1
    assert (scenes[0].start, scenes[0].end) == (62, 65)
    assert scenes[0].can_skip(6660, True)
    assert not scenes[0].can_skip(6300, True)


def test_fallback_only_for_missing_times_and_unused_sources():
    complete = Scene("one", 10, 20, "violence", "doesthedogdie")
    missing = Scene("two", None, None, "violence", "doesthedogdie")
    assert fallback_providers([complete]) == []
    assert fallback_providers([complete, missing]) == [CleanStream, CringeMDb]
    supplied = Scene("external", 30, 40, "violence", "CleanStream / VideoSkip")
    assert fallback_providers([missing, supplied]) == [CringeMDb]
