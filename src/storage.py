import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(self.db_path)

    def save(self, df):
        """Replace all movie rows in one transaction."""
        connection = get_connection(self.db_path)

        try:
            # convert missing values to None
            df = df.astype(object).where(pd.notna(df), None)

            # delete existing movie rows
            connection.execute("DELETE FROM movies")

            # insert new movie rows
            for _, row in df.iterrows():
                connection.execute(
                    """
                    INSERT INTO movies (title, release_year, rating, genre)
                    VALUES (?, ?, ?, ?)
                    """,
                    tuple(row[column] for column in MOVIE_COLUMNS)
                )

            connection.commit()

            logger.debug(
                f"Stored movies in SQLite: rows={len(df)}"
            )

        except sqlite3.Error:
            connection.rollback()
            raise

        finally:
            connection.close()

    def get(self):
        """Return the four movie columns as a DataFrame, ordered by id."""
        connection = get_connection(self.db_path)

        try:
            # selects the four fields
            cursor = connection.execute(
                """
                SELECT title, release_year, rating, genre
                FROM movies
                ORDER BY id
                """
            )
            # fetch rows
            rows = cursor.fetchall()

            # create DF
            return pd.DataFrame(
                [dict(row) for row in rows],
                columns=MOVIE_COLUMNS
            )

        finally:
            connection.close()

    def select_columns(self, columns, limit=5):
        """Return id plus the requested movie columns, ordered by id."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)

        try:
            cursor = connection.execute(
                f"""
                SELECT {selected_columns}
                FROM movies
                ORDER BY id
                LIMIT ?
                """,
                (limit,)
            )
            # returns list of dictionaries
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            logger.debug(
                f"Selected columns: {columns}, rows={len(results)}"
            )

            return results

        finally:
            connection.close()

    def count_movies(self):
        """Return the number of stored movies using SQL COUNT(*)."""
        connection = get_connection(self.db_path)

        try:
            cursor = connection.execute(
                "SELECT COUNT(*) FROM movies"
            )

            return cursor.fetchone()[0]

        finally:
            connection.close()

    def query_movies(self, columns, min_rating, limit):
        """Return selected fields from matching movies using SQL."""
        # requires column to be selected
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        # validates column is named in db
        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)

        try:
            cursor = connection.execute(
                f"""
                SELECT {selected_columns}
                FROM movies
                WHERE rating >= ?
                ORDER BY rating DESC, id ASC
                LIMIT ?
                """,
                (min_rating, limit)
            )

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            logger.debug(
                f"Queried columns: {columns}, rows={len(results)}"
            )

            return results

        finally:
            connection.close()
