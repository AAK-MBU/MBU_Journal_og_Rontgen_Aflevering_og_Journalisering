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


_EDI_REDIRECT_QUERY = """
    SELECT [target_provider_number], [target_phone_number], [edi_subject_suffix]
    FROM [RPA].[rpa].[ProviderNumberRedirects]
    WHERE [source_provider_number] = ?
      AND [scope] = N'EDI'
      AND [is_active] = 1
"""


def get_edi_redirect(contractor_id: str | None) -> dict | None:
    """
    Look up an active EDI recipient redirect in the RPA database.

    Some clinics exist in Solteq under their own provider number (ydernummer),
    but are reached through a shared recipient in the EDI portal (e.g. Hasle
    Torv and Brobjergparken -> 485055). These redirects are maintained in
    [RPA].[rpa].[ProviderNumberRedirects] with scope 'EDI' (managed via
    automation-hub). 'SOLTEQ' rows are handled upstream by the journalizing
    process and are already reflected in the clinic set on the patient.

    A failing lookup raises: it must not silently fall back to the clinic's
    own number, as that could send to the wrong recipient.

    Args:
        contractor_id (str | None): The clinic's provider number as registered in Solteq.

    Returns:
        dict | None: {"contractor_id": str, "phone_number": str | None,
        "subject_suffix": str | None}, or None if no active EDI redirect.
        phone_number None means: keep the clinic's own phone number.
    """
    contractor_id = (contractor_id or "").strip()
    if not contractor_id:
        return None

    with RPAConnection(db_env="PROD", commit=False) as rpa_conn:
        rows = rpa_conn.execute_query(
            _EDI_REDIRECT_QUERY, [contractor_id], return_dict=True
        )

    if not rows:
        return None

    row = rows[0]
    suffix = (row["edi_subject_suffix"] or "").strip() or None
    return {
        "contractor_id": row["target_provider_number"],
        "phone_number": row["target_phone_number"],
        "subject_suffix": suffix,
    }


def apply_edi_redirect(extern_clinic_data: list, edi_redirect: dict | None) -> list:
    """
    Return extern clinic data as the EDI portal should see it.

    Same as extern_clinic_data, but with contractorId/phoneNumber replaced by
    the EDI recipient when an EDI redirect applies. The input is not modified.
    """
    if not extern_clinic_data or not edi_redirect:
        return extern_clinic_data
    clinic = dict(extern_clinic_data[0])
    clinic["contractorId"] = edi_redirect["contractor_id"]
    if edi_redirect.get("phone_number"):
        clinic["phoneNumber"] = edi_redirect["phone_number"]
    return [clinic, *extern_clinic_data[1:]]


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
    finally:
        cursor.close()
