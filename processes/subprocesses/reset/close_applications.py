"""This module contains functions to close the Solteq Tand application and its patient window."""

import logging

logger = logging.getLogger(__name__)


def close_patient_window(app_instance) -> None:
    """Closes the patient window in the Solteq Tand application if it is open.

    This runs between work items, including while an exception is already
    propagating, so every failure is logged and swallowed rather than
    masking the error that caused the item to fail.

    Args:
        app_instance: The SolteqTandApp instance, or None if Solteq is not running.
    """
    if not app_instance:
        logger.info("No Solteq Tand instance available. Skipping patient window close.")
        return

    try:
        logger.info("Close patient window.")
        app_instance.close_patient_window()
    except Exception as error:  # pylint: disable=broad-except
        logger.error("Error closing patient window: %s", error)


def close_solteq_tand(app_instance) -> None:
    """Closes the Solteq Tand application if it is running.

    Args:
        app_instance: The SolteqTandApp instance, or None if Solteq is not running.
    """
    if not app_instance:
        logger.info("No Solteq Tand instance available. Skipping close operations.")
        return

    try:
        logger.info("Close Solteq Tand.")
        app_instance.close_solteq_tand()
        logger.info("Solteq Tand closed.")
    except Exception as error:  # pylint: disable=broad-except
        logger.error("Error closing Solteq Tand: %s", error)
