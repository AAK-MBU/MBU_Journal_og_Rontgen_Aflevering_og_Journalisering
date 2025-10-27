"""Utility functions for RPA operations"""

from typing import Any

import pyodbc
from mbu_dev_shared_components.database.connection import RPAConnection


def get_rpa_constant(constant_name: str) -> str:
    """
    Get a constant value from RPA connection

    Args:
        constant_name (str): Name of the constant to retrieve

    Returns:
        str: The constant value, empty string if not found
    """
    with RPAConnection(db_env="PROD", commit=False) as rpa_conn:
        return rpa_conn.get_constant(constant_name).get("value", "")


def get_rpa_credentials(credential_name: str) -> dict[str, Any]:
    """
    Get credentials from RPA connection

    Args:
        credential_name (str): Name of the credential to retrieve

    Returns:
        dict[str, Any]: Dictionary containing username, password,
                       and other credential data
    """
    with RPAConnection(db_env="PROD", commit=False) as rpa_conn:
        return rpa_conn.get_credential(credential_name)


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
        result = [dict(zip(columns, row)) for row in rows]
        return result
    finally:
        cursor.close()
