import sqlite3
from pathlib import Path


def get_connection(db_path):
    """Return a fresh connection with rows accessible by column name."""
    db_path = Path(db_path)

    # create the parent directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # connect to the database
    connection = sqlite3.connect(db_path)

    # allow rows to be accessed via column name
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database(db_path):
    """Create the movie table if it does not exist."""
    connection = get_connection(db_path)

    # creates movie table if it doesn't exist with id, title, release_year, rating, genre
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY,
                title TEXT,
                release_year INTEGER,
                rating REAL,
                genre TEXT
            )
        """)

        connection.commit()

    finally:
        connection.close()
