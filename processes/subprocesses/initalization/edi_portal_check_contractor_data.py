"""
This module contains a function to check if the contractor ID is valid.
"""

import logging

from application_handler import get_app
from mbu_rpa_core.exceptions import BusinessError, ProcessError

from helpers.context_handler import get_context_values
from helpers.credential_constants import get_rpa_constant
from processes.subprocesses.db_utils import get_exceptions

logger = logging.getLogger(__name__)


def check_contractor_data() -> None:
    """
    Check if the contractor ID is valid.

    Raises:
        BusinessError: If a business rule is broken.
    """
    try:
        # Get the application instance
        solteq_app = get_app()

        if solteq_app is None:
            raise ValueError("Could not get application instance.")

        solteq_app.open_edi_portal()

        logger.info("Checking if contractor id is set...")

        contractor_check = solteq_app.edi_portal_check_contractor_id(
            extern_clinic_data=get_context_values("extern_clinic_data"),
        )

        rpa_db_conn = get_rpa_constant("DbConnectionString")
        if contractor_check["rowCount"] == 0:
            excp = get_exceptions(rpa_db_conn)
            message = [d for d in excp if d["exception_code"] == "1G"][0][
                "message_text"
            ]
            raise BusinessError(message)
        if contractor_check["isPhoneNumberMatch"] is False:
            excp = get_exceptions(rpa_db_conn)
            message = [d for d in excp if d["exception_code"] == "1H"][0][
                "message_text"
            ]
            raise BusinessError(message)
    except BusinessError:
        raise
    except Exception as error:
        logger.error("Process error occurred: %s", error)
        raise ProcessError("A process error occurred.") from error
