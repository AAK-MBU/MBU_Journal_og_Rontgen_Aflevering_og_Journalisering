"""This module handles the retrieval of images from Romexis."""

import logging
import os

from mbu_dev_shared_components.romexis.db_handler import RomexisDbHandler
from mbu_rpa_core.exceptions import BusinessError, ProcessError

from helpers import config
from helpers.credential_constants import get_rpa_constant
from processes.subprocesses.process.romexis.db_handler import (
    get_image_data,
    get_person_info,
)
from processes.subprocesses.process.romexis.image_handler import (
    clear_img_files_in_folder,
    process_images_threaded,
)
from processes.subprocesses.process.romexis.zip_handler import (
    create_zip_from_images,
)

logger = logging.getLogger(__name__)


def get_images_from_romexis(queue_element_data) -> tuple[str, str] | None:
    """
    Fetches images from the Romexis database.

    Returns:
        list: A list of dictionaries containing image data.
    """
    try:
        logger.info("Fetching images from Romexis database.")
        romexis_db_conn = get_rpa_constant("romexis_db_connstr")

        # Enhance connection string to handle intermittent connectivity
        # Use correct ODBC parameter names (with spaces, not underscores)
        # Connection Timeout: Increase from default 15s to 30s
        # MultipleActiveResultSets: Allow multiple active result sets
        enhancements = []
        if "Connection Timeout" not in romexis_db_conn:
            enhancements.append("Connection Timeout=30")
        if "MultipleActiveResultSets" not in romexis_db_conn:
            enhancements.append("MultipleActiveResultSets=True")

        if enhancements:
            # Ensure connection string ends properly
            conn_base = romexis_db_conn.rstrip(";")
            romexis_db_conn = conn_base + ";" + ";".join(enhancements)
            logger.info("Enhanced connection string with: %s", enhancements)

        romexis_db_handler = RomexisDbHandler(conn_str=romexis_db_conn)
        ssn = queue_element_data.get("patient_cpr")
        destination_path = os.path.join(config.TMP_FOLDER, ssn, "img")

        person_info = get_person_info(romexis_db_handler, ssn)
        if person_info is None:
            logger.info("No person info retrieved.")
            return None
        person_id, person_name = person_info

        images_data = get_image_data(romexis_db_handler, person_id)
        if not images_data:
            logger.info("No images found for the patient.")
            return None

        process_images_threaded(
            images_data, destination_path, ssn, person_name, romexis_db_handler
        )

        logger.info("Removing .img-files from temp folder.")
        clear_img_files_in_folder(folder_path=destination_path)

        logger.info("Zipping images.")
        zip_full_path, zip_filename = create_zip_from_images(
            ssn=ssn, person_name=person_name, source_folder=destination_path
        )

        return zip_full_path, zip_filename
    except BusinessError as be:
        logger.error("Business error: %s", be)
        raise be
    except ProcessError as e:
        logger.error("Failed to fetch images from Romexis: %s", e)
        raise e
