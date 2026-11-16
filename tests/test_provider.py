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


def test_tv_episode_isolation():
    item = {"id": 1393484, "name": "Eşref Rüya", "releaseYear": 2025,
            "itemTypeName": "TV Show"}
    categories = [{"id": 4, "name": "Violence & Gore"}]
    topics = [{"id": 2, "name": "blood", "topicCategoryId": 4}]
    ratings = [
        {"id": 5, "itemId": 1393484, "topicId": 2, "yes": 1,
         "index1": 1, "index2": 2, "position1": 0, "position2": 1,
         "position3": 0, "safePosition1": 0, "safePosition2": 1,
         "safePosition3": 30, "isSceneAlert": True},
        {"id": 6, "itemId": 1393484, "topicId": 2, "yes": 1,
         "index1": 1, "index2": 3, "position1": 0, "position2": 5,
         "position3": 0, "safePosition1": 0, "safePosition2": 5,
         "safePosition3": 30, "isSceneAlert": True},
    ]
    first = normalize(item, item, ratings, topics, categories, 1, 2)
    second = normalize(item, item, ratings, topics, categories, 1, 3)
    assert first.external_id == "1393484:S1E2"
    assert second.external_id == "1393484:S1E3"
    assert [s.key for s in first.scenes] == ["doesthedogdie:5"]
    assert [s.key for s in second.scenes] == ["doesthedogdie:6"]
