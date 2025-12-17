"""Module to handle item processing"""

import datetime
import logging
import os
import time
import zoneinfo

from mbu_dev_shared_components.solteqtand.application import SolteqTandApp
from mbu_dev_shared_components.solteqtand.database import SolteqTandDatabase
from mbu_rpa_core.exceptions import BusinessError, ProcessError

from helpers import config
from helpers.context_handler import get_context_values, set_context_values
from helpers.credential_constants import get_rpa_constant
from processes.application_handler import close, get_app, hard_close
from processes.subprocesses.dashboard.dashboard_data_handler import (
    update_dashboard_step_run,
)
from processes.subprocesses.initalization.initalize import (
    initalization_checks_and_get_data,
)
from processes.subprocesses.process.document.create_medical_record import (
    check_and_create_medical_record_document,
)
from processes.subprocesses.process.edi.edi_portal_handler import (
    EdiContext,
    edi_portal_handler,
)
from processes.subprocesses.process.edi.get_files_for_edi_portal import (
    prepare_edi_portal_documents,
)
from processes.subprocesses.process.romexis.romexis_images_handler import (
    get_images_from_romexis,
)

logger = logging.getLogger(__name__)


def _validate_input_data(item_data: dict) -> None:
    """Validate input data for processing."""
    if (
        "new_clinic_ydernummer" not in item_data
        or "new_clinic_phone_number" not in item_data
    ):
        raise ValueError("Missing new clinic ydernummer or phone number in item data.")


def _setup_context(item_data: dict, item_id: int) -> None:
    """Set up context variables for further processing."""
    set_context_values(
        cpr=item_data.get("cpr"),
        item_id=item_id,
        new_clinic_ydernummer=item_data.get("new_clinic_ydernummer")
        if "new_clinic_ydernummer" in item_data
        else None,
        new_clinic_phone_number=item_data.get("new_clinic_phone_number")
        if "new_clinic_phone_number" in item_data
        else None,
        patient_name=item_data.get("name"),
        api_context={
            "endpoint": os.environ.get("DASHBOARD_API_URL"),
            "api_key": os.environ.get("API_ADMIN_TOKEN"),
            "headers": {"X-API-Key": os.environ.get("API_ADMIN_TOKEN")},
        },
    )


def _prepare_environment() -> None:
    """Prepare the environment by closing necessary applications."""
    # Make sure Adobe Acrobat Reader and MSEdge is closed before starting the process
    hard_close("AcroRd32.exe")
    hard_close("msedge.exe")


def _open_and_initialize_patient(solteq_app, item_data: dict) -> SolteqTandDatabase:
    """Open and initialize the patient in Solteq Tand application."""
    logger.info("Opening patient in Solteq Tand application...")
    solteq_app.open_patient(get_context_values("cpr"))

    logger.info("Initalization checks and getting data for further processing.")
    initalization_checks_and_get_data(item_data)

    # Initialize the Solteq Tand database instance
    solteq_app_db_conn = get_rpa_constant("solteq_tand_db_connstr")
    solteq_tand_db_object = SolteqTandDatabase(conn_str=solteq_app_db_conn)

    return solteq_tand_db_object


def _process_images() -> None:
    """Get images from Romexis and create a zip file."""
    logger.info("Fetching images from Romexis.")
    images_result = get_images_from_romexis()
    if images_result is not None:
        zip_path, zip_filename = images_result
        logger.info("Zip file created: %s with filename: %s", zip_path, zip_filename)


def _process_medical_record(solteq_tand_db_object) -> str:
    """Process medical record document and get file paths for EDI upload."""
    logger.info("Checking and creating medical record document if not already created.")
    check_and_create_medical_record_document(
        solteq_tand_db_object=solteq_tand_db_object
    )

    # Get all documents needed for EDI Portal upload.
    logger.info("Preparing EDI Portal documents for upload.")
    joined_file_paths = prepare_edi_portal_documents(
        solteq_tand_db_object=solteq_tand_db_object
    )

    return joined_file_paths


def _process_edi_portal(
    solteq_app: SolteqTandApp,
    item_data: dict,
    joined_file_paths: str,
) -> str | None:
    """Process EDI Portal upload and sending material."""
    solteq_app.open_edi_portal()
    time.sleep(5)

    # Send the documents trough the EDI Portal to the new dentist.
    try:
        ctx = EdiContext(
            extern_clinic_data=get_context_values("extern_clinic_data"),
            queue_element=item_data,
            path_to_files_for_upload=joined_file_paths,
            journal_note=get_context_values("administrative_note_description"),
        )
        receipt_pdf = edi_portal_handler(context=ctx)
        solteq_app.close_edi_portal()
        return receipt_pdf
    except Exception as e:
        solteq_app.close_edi_portal()
        raise ProcessError("An error occurred in the EDI Portal process.") from e


def _finalize_edi_portal_document(
    solteq_tand_db_object: SolteqTandDatabase,
    receipt_pdf: str,
    solteq_app: SolteqTandApp,
) -> None:
    # Check if the receipt PDF was created successfully and upload it to Solteq Tand.
    logger.info("Checking for existing EDI Portal documents.")
    local_tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.datetime.now(tz=local_tz)
    edi_receipt_date_one_month_ago = now - datetime.timedelta(days=30)
    list_of_documents = solteq_tand_db_object.get_list_of_documents(
        filters={
            "p.cpr": get_context_values("cpr"),
            "ds.OriginalFilename": f"%EDI Portal - {get_context_values('patient_name')}%",
            "ds.rn": "1",
            "ds.DocumentStoreStatusId": "1",
            "ds.DocumentCreatedDate": (">=", edi_receipt_date_one_month_ago),
        }
    )
    logger.info("Found %d existing EDI Portal document.", len(list_of_documents))

    if not list_of_documents:
        logger.info("No existing EDI Portal document found, creating a new one.")
        solteq_app.create_document(document_full_path=receipt_pdf)
        logger.info("EDI Portal document was created successfully.")
    else:
        logger.info("EDI Portal document already exists, skipping creation.")


def _created_administrative_note(
    solteq_app: SolteqTandApp,
    solteq_tand_db_object: SolteqTandDatabase,
) -> None:
    """Check if administrative note exists if not create it."""
    logger.info("Checking if administrative note exists.")

    local_tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.datetime.now(tz=local_tz)
    journal_note_date_one_month_ago = now - datetime.timedelta(days=30)

    filter_params = {
        "p.cpr": get_context_values("cpr"),
        "dn.Beskrivelse": f"%{config.ADM_NOTE_LOOKUP}%",
        "ds.Dokumenteret": (">=", journal_note_date_one_month_ago),
    }

    result = solteq_tand_db_object.get_list_of_journal_notes(
        filters=filter_params, order_by="ds.Dokumenteret", order_direction="DESC"
    )

    if not result:
        logger.info("Creating administrative note.")
        solteq_app.create_journal_note(
            note_message=config.ADM_NOTE, checkmark_in_complete=True
        )
        logger.info("Administrative note created successfully.")
    else:
        logger.info("Administrative note already exists, skipping creation.")


def process_item(item_data: dict, item_id: int) -> None:
    """Function to handle item processing"""

    try:
        # Validate clinical input data
        _validate_input_data(item_data)

        # Set context variables for further processing
        _setup_context(item_data, item_id)

        # Update dashboard step run as running
        update_dashboard_step_run(
            step_name=config.DASHBOARD_STEP_8_NAME, status="running"
        )

        # Get the application instance
        solteq_app = get_app()

        if solteq_app is None:
            raise ValueError("Could not get application instance.")

        # Make sure Adobe Acrobat Reader and MSEdge is closed before starting the process
        _prepare_environment()

        # Open and initialize the patient in Solteq Tand application
        # and run necessary initalization checks
        solteq_tand_db_object = _open_and_initialize_patient(solteq_app, item_data)

        # Get images from Romexis and create a zip file.
        _process_images()

        # Process medical record document and get file paths for EDI upload.
        joined_file_paths = _process_medical_record(solteq_tand_db_object)

        # Process EDI Portal upload and sending material.
        receipt_pdf = _process_edi_portal(
            solteq_app=solteq_app,
            item_data=item_data,
            joined_file_paths=joined_file_paths,
        )

        if receipt_pdf is not None:
            _finalize_edi_portal_document(
                solteq_tand_db_object=solteq_tand_db_object,
                receipt_pdf=receipt_pdf,
                solteq_app=solteq_app,
            )
        else:
            logger.warning(
                "No receipt PDF was generated from EDI Portal process; skipping document finalization."
            )

        # Check if administrative note exists if not create it.
        _created_administrative_note(
            solteq_app=solteq_app,
            solteq_tand_db_object=solteq_tand_db_object,
        )

        # Update dashboard step run as success
        update_dashboard_step_run(
            step_name=config.DASHBOARD_STEP_8_NAME, status="success"
        )
    except BusinessError as be:
        logger.error("Business error occurred: %s", be)
        update_dashboard_step_run(
            step_name=config.DASHBOARD_STEP_8_NAME,
            status="failed",
            failure=be,
            rerun=True,
        )
        raise be
    except Exception as e:
        logger.error("%s", e)
        update_dashboard_step_run(
            step_name=config.DASHBOARD_STEP_8_NAME,
            status="failed",
            failure=e,
            rerun=False,
        )
        raise ProcessError("A process error occurred.") from e
    finally:
        close()
