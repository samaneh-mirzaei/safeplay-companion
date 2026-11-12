from safeplay.provider import category_for, normalize, hms


def test_normalize_verified_and_community():
    item = {"id": 1, "name": "Movie", "releaseYear": 2020, "itemTypeName": "Movie"}
    categories = [{"id": 4, "name": "Violence & Gore"}]
    topics = [{"id": 2, "name": "blood", "topicCategoryId": 4}]
    ratings = [
        {"id": 5, "itemId": 1, "topicId": 2, "yes": 1, "position1": 0,
         "position2": 1, "position3": 0, "safePosition1": 0, "safePosition2": 1,
         "safePosition3": 30, "isSceneAlert": True},
        {"id": 6, "itemId": 1, "topicId": 2, "yes": 1, "position1": 0,
         "position2": 2, "position3": 0, "safePosition1": 0, "safePosition2": 2,
         "safePosition3": 30, "isSceneAlert": False},
    ]
    movie = normalize(item, item, ratings, topics, categories)
    assert [s.reliability for s in movie.scenes] == ["verified", "community"]
    assert movie.scenes[0].start == 60
    assert movie.scenes[0].end == 90


def test_bad_time_and_category():
    assert hms({"position1": 0, "position2": 80, "position3": 0}, "position") is None
    assert category_for("Unknown theme") is None
