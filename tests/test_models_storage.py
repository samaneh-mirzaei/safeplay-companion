from safeplay.models import Movie, Scene, identify_file, runtime_warning
from safeplay.storage import Store


def test_filename_and_runtime():
    assert identify_file("D:/Movie.Name.2020.1080p.mkv") == ("Movie Name", 2020)
    assert runtime_warning(7200, 7500)


def test_cache_and_edits_survive_refresh(tmp_path):
    db = Store(tmp_path / "db.sqlite")
    original = Scene("source:1", 10, 20, "violence", "source", "community")
    movie = Movie("Film", 2020, "1", 100, "source", [original])
    db.save_guide(movie)
    assert db.load_guide("1").scenes[0].reliability == "community"
    edited = Scene("source:1", 11, 22, "violence", "source", "community")
    db.save_edit("1", edited, reviewed=True)
    movie.scenes[0].start = 12
    db.save_guide(movie)
    loaded = db.load_guide("1")
    assert (loaded.scenes[0].start, loaded.scenes[0].reliability) == (11, "manual")
    db.close()
