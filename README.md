# Movie API

This application is a movie API built with FastAPI. Users can upload a CSV file of movies, which is saved in a SQLite database. The 'storage.py' module handles saving and retrieving movie data, while 'models.py' defines the data structures used by the API. The 'data_pipeline' module handles validating and processing the movies, including removing duplicates, missing values, and outliers. The 'cache.py' module uses FakeRedis to temporarily store movie retrieval results so repeated requests can be returned faster. The cache is cleared whenever movies are uploaded or processed so that it always reflects the latest database data.

## Running the API

```bash
python -m uvicorn main:app --reload
```

Open the API documentation at http://127.0.0.1:8000/docs.

## Running the tests

```bash
python -m pytest tests -v
```

## Sample processing request

Send a POST request to `/movies/process` with the following:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {
      "enabled": true,
      "axis": "rows"
    },
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

Expected result: 
The original 20 movie rows are reduced to 16 rows. Two duplicate rows and two outlier rows are removed.