"""This module contains functions to interact with the database."""

import logging

import pyodbc

logger = logging.getLogger(__name__)


def get_exceptions(db_connection: str) -> list[dict]:
    """Get exceptions from the database."""
    conn = pyodbc.connect(db_connection)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                [exception_code]
                ,[message_text]
            FROM
                [RPA].[rpa].[BusinessExceptionMessages]
            """
        )
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        result = [dict(zip(columns, row, strict=True)) for row in rows]
        return result
    except Exception as e:
        logger.error("Error fetching exceptions: %s", e)
        return []
    finally:
        cursor.close()
        conn.close()
