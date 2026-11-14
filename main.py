import io
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from src import (
    HealthResponse,
    setup_logging,
    ProcessConfig,
    log_requests,
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    MovieCache
)
from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src.storage import MOVIE_COLUMNS

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Movie API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()
cache = MovieCache()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    # checks that application is responding, doesn't read or store any data
    return {"status": "ok", "version": "1.0.0"}


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read and store a CSV upload."""

    # checks file extension, makes lowercase
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    # ensures the file is a CSV
    if extension != ".csv":
        logger.warning("Unsupported file format: %s", extension)
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported."
        )

    # reads the uploaded file as bytes, await makes it async
    contents = await file.read()

    # parse CSV
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        ValueError,
    ):
        # if parsing fails returns status 400 warning
        logger.warning("Unable to read CSV file: %s", filename)
        raise HTTPException(
            status_code=400,
            detail="Unable to read CSV file."
        )

    # checks that the CSV has exactly the four required movie columns
    if len(df.columns) != len(MOVIE_COLUMNS) or set(df.columns) != set(MOVIE_COLUMNS):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain exactly these columns: {MOVIE_COLUMNS}"
        )

    # makes sure the CSV contains at least one movie
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain at least one movie."
        )

    # puts columns in the required order
    df = df[MOVIE_COLUMNS]

    # saves the movies in the database
    storage.save(df)
    cache.invalidate()

    logger.info(
        "Uploaded movies: filename=%s, rows=%s",
        filename,
        len(df)
    )

    # returns information about the uploaded file
    return MovieUploadInfo(
        filename=filename,
        rows=len(df),
        columns=len(df.columns),
        column_names=list(df.columns),
    )



@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit rows from the stored movies."""

    # checks whether this response is already cached
    cached_response = cache.get(limit)

    # if the response is cached, return it without querying the database
    if cached_response is not None:
        logger.info("Returned cached movies: limit=%s", limit)
        return cached_response

    # gets the selected movie rows from storage
    data = storage.select_columns(MOVIE_COLUMNS, limit)

    # gets the total number of movies in the database
    total_rows = storage.count_movies()

    # creates the complete response
    response = {
        "data": data,
        "total_rows": total_rows
    }

    # saves the response in the cache for future requests
    cache.set(limit, response)

    logger.info(
        "Retrieved movies: returned_rows=%s",
        len(data)
    )

    return response



@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    """Search movies by minimum rating and selected columns."""

    try:
        # gets movies matching the minimum rating and selected columns
        data = storage.query_movies(columns, min_rating, limit)

    # if the columns are invalid, returns status 400
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    logger.info(
        "Queried movies: columns=%s, min_rating=%s, returned_rows=%s",
        columns,
        min_rating,
        len(data)
    )

    return data


@app.post(
    "/movies/process",
    response_model=MovieProcessingReport
)
def process_movies(config: ProcessConfig):
    """Validate and process the stored movies using MP1 functions."""

    # gets a copy of the saved movies
    df = storage.get()

    # if there are no movies in storage, return 400
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No movies have been uploaded."
        )

    # convert the request to dictionary
    settings = config.model_dump()

    # check that every requested numeric column exists, 400 if not
    numeric_columns = settings["validation"]["numeric_columns"]

    for column in numeric_columns:
        if column not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Numeric column '{column}' not found.",
            )

    try:
        # validate the movies using the requested columns
        validated_df = validate_dataframe(
            df,
            required_columns=settings["validation"]["required_columns"],
            numeric_columns=numeric_columns,
        )

        # count how many rows validation removed
        validation_rows_removed = len(df) - len(validated_df)

        # keep a copy to compare against cleaned result
        validated_copy = validated_df.copy()

        # process the validated data using the full config
        processed_df = process_data(validated_df, settings)

        # create a report comparing before and after cleaning
        cleaning_report = create_cleaning_report(
            validated_copy,
            processed_df,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    # save the processed movies only after the steps succeeded
    storage.save(processed_df)
    cache.invalidate()

    logger.info(
        "Processed movies: validation_removed=%s, "
        "rows_before=%s, rows_after=%s",
        validation_rows_removed,
        cleaning_report["rows_before"],
        cleaning_report["rows_after"],
    )

    # return the processing report
    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }
