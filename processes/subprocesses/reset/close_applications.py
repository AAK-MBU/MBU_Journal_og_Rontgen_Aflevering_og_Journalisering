"""This module contains functions to close the Solteq Tand application and its patient window."""

import logging

from mbu_rpa_core.exceptions import ProcessError

from processes.application_handler import get_app

logger = logging.getLogger(__name__)
application = get_app()


def close_patient_window(app_instance) -> None:
    """Closes the patient window in the Solteq Tand application if it exists."""
    if hasattr(app_instance, "solteq_tand_app") and app_instance.solteq_tand_app:
        try:
            logger.info("Close patient window.")
            app_instance.solteq_tand_app.close_patient_window()
        except ProcessError as error:
            logger.error("Error closing patient window: %s", error)


def close_solteq_tand(app_instance) -> None:
    """Closes the Solteq Tand application if it exists."""
    if hasattr(app_instance, "solteq_tand_app") and app_instance.solteq_tand_app:
        try:
            logger.info("Close Solteq Tand.")
            app_instance.solteq_tand_app.close_solteq_tand()
            logger.info("Solteq Tand closed.")
        except ProcessError as error:
            logger.error("Error closing Solteq Tand: %s", error)
    else:
        logger.info("solteq_tand_app attribute not found. Skipping close operations.")
