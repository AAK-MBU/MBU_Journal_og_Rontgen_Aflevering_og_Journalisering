"""Module for handling application startup, and close"""

import logging
import subprocess as sp
from subprocess import CalledProcessError

from mbu_dev_shared_components.solteqtand.application import SolteqTandApp

from helpers import config
from helpers.credential_constants import get_rpa_credentials

APP = None
logger = logging.getLogger(__name__)


def get_app():
    """Function to get the application instance"""
    # ruff: noqa: PLW0602
    global APP
    return APP


def startup():
    """Function for starting applications"""
    logger.info("Starting applications...")

    logger.info("Starting Solteq Tand application...")
    try:
        creds = get_rpa_credentials("solteq_tand_svcrpambu001")
        username = creds["username"]
        password = creds["decrypted_password"]

        application = SolteqTandApp(
            app_path=config.APP_PATH, username=username, password=password
        )
        application.start_application()
        application.login()

        global APP  # ruff: noqa: PLW0602
        APP = application
    except Exception as e:
        logger.error("Failed to start Solteq Tand application: %s", e)
        raise


def soft_close() -> None:
    """Function for closing applications softly"""
    logger.info("Closing applications softly...")

    logger.info("Closing Solteq Tand application softly...")
    application = get_app()
    try:
        application.close_solteq_tand()
        logger.info("Closed application softly")
    except Exception as e:
        logger.error("Could not close application softly: %s", e)


def hard_close(application: str) -> None:
    """Function for closing applications hard"""
    logger.info("Hard closing %s...", application)
    list_processes = ["wmic", "process", "get", "description"]
    if f"{application}" in sp.check_output(list_processes).strip().decode():
        try:
            kill_msg = sp.check_output(["taskkill", "/f", "/im", f"{application}"])
            logger.info(kill_msg)
        except CalledProcessError as e:
            logger.error(
                f"{application} found in subprocesses, but error while killing it: %s",
                e,
            )


def close():
    """Function for closing applications softly or hardly if necessary"""
    solteq_app = get_app()
    if solteq_app:
        soft_close()
    solteq_app = get_app()
    if solteq_app:
        hard_close(application="TMTand.exe")

    # Make sure Adobe Acrobat Reader and MSEdge is closed before starting the process
    hard_close("AcroRd32.exe")
    hard_close("msedge.exe")


def reset():
    """Function for resetting application"""
    logger.info("Resetting applications...")
    close()
    startup()
