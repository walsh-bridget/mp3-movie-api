import pytest
from src import MovieStorage
import main

import pandas as pd 


def test_movies_persist(client, test_storage, uploaded_movies):
    # create another storage object using the same database
    second_storage = MovieStorage(test_storage.db_path)

    # get the movies and count them
    movies = second_storage.get()
    total = second_storage.count_movies()

    # check 20 rows and all four columns
    assert total == 20
    assert len(movies) == 20
    assert list(movies.columns) == [
        "title", "release_year", "rating", "genre"
    ]

    # compare the database titles with the original csv
    expected_movies = pd.read_csv("fixtures/sample_movies.csv")
    assert movies["title"].tolist() == expected_movies["title"].tolist()

    # compare ids from storage with ids from the api
    stored_movies = second_storage.select_columns(
        ["title", "release_year", "rating", "genre"], limit=100
    )
    response = client.get("/movies?limit=100")

    assert response.status_code == 200

    storage_ids = [movie["id"] for movie in stored_movies]
    api_ids = [movie["id"] for movie in response.json()["data"]]

    assert storage_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))
    assert storage_ids == api_ids


def test_cache_and_processing(client, uploaded_movies, processing_body):
    # retrieve movies with two different limits
    response_100 = client.get("/movies?limit=100")
    response_1 = client.get("/movies?limit=1")

    assert response_100.status_code == 200
    assert response_1.status_code == 200

    # check that both responses were cached
    assert main.cache.get(100) == response_100.json()
    assert main.cache.get(1) == response_1.json()

    # repeat the request to check the cached response
    repeated_response = client.get("/movies?limit=100")
    assert repeated_response.json() == response_100.json()

    # process the movies
    process_response = client.post(
        "/movies/process",
        json=processing_body
    )

    assert process_response.status_code == 200
    report = process_response.json()

    assert report["validation_rows_removed"] == 0
    assert report["cleaning_report"]["rows_before"] == 20
    assert report["cleaning_report"]["rows_after"] == 16

    # processing should clear the old cache entries
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    # retrieve the processed movies
    updated_response = client.get("/movies?limit=100")

    assert updated_response.status_code == 200
    updated_data = updated_response.json()

    assert updated_data["total_rows"] == 16
    assert [movie["title"] for movie in updated_data["data"]] == [
        "Movie " + letter for letter in "ABCDEFGHIJKLMNOP"
    ]
    assert [movie["id"] for movie in updated_data["data"]] == list(range(1, 17))

    # check that the new response was cached
    assert main.cache.get(100) == updated_data


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # make the first request to populate the cache
    first_response = client.get("/movies?limit=100")
    assert first_response.status_code == 200

    # replace database methods with functions that fail if called
    def fail_if_called(*args, **kwargs):
        raise AssertionError("database should not be queried on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    # make the same request again
    second_response = client.get("/movies?limit=100")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
