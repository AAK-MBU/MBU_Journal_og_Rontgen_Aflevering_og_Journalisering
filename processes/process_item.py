"""Module to handle item processing"""

import datetime
import logging
import time

from dateutil.relativedelta import relativedelta
from mbu_dev_shared_components.solteqtand.database import SolteqTandDatabase
from mbu_rpa_core.exceptions import BusinessError, ProcessError

from helpers.app_context import app_context
from helpers.credential_constants import get_rpa_constant
from processes.application_handler import close, get_app, hard_close
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


def process_item(item_data: dict, item_reference: str):
    """Function to handle item processing"""

    try:
        # Get the application instance
        solteq_app = get_app()

        if solteq_app is None:
            raise ValueError("Could not get application instance.")

        # Make sure Adobe Acrobat Reader and MSEdge is closed before starting the process
        hard_close("AcroRd32.exe")
        hard_close("msedge.exe")

        # Set the queue element data
        queue_element_data = item_data
        queue_element_data["patient_cpr"] = queue_element_data["patient_cpr"].replace(
            "-", ""
        )

        # Open the patient in Solteq Tand application
        # It is used for initialization checks and later processes
        logger.info("Opening patient in Solteq Tand application...")
        solteq_app.open_patient(queue_element_data.get("patient_cpr"))

        logger.info("Initalization checks and getting data for further processing.")
        initalization_checks_and_get_data(queue_element_data)

        # Initialize the Solteq Tand database instance
        solteq_app_db_conn = get_rpa_constant("solteq_tand_db_connstr")
        solteq_tand_db_object = SolteqTandDatabase(conn_str=solteq_app_db_conn)

        # Get images from Romexis and create a zip file.
        logger.info("Fetching images from Romexis.")
        images_result = get_images_from_romexis(queue_element_data=queue_element_data)
        if images_result is not None:
            zip_path, zip_filename = images_result
            logger.info(
                "Zip file created: %s with filename: %s", zip_path, zip_filename
            )

        # Call the function to check and create the digital printed journal if needed.
        logger.info(
            "Checking and creating medical record document if not already created."
        )
        check_and_create_medical_record_document(
            queue_element_data=queue_element_data,
            solteq_tand_db_object=solteq_tand_db_object,
        )

        # Get all documents needed for EDI Portal upload.
        logger.info("Preparing EDI Portal documents for upload.")
        joined_file_paths = prepare_edi_portal_documents(
            solteq_tand_db_object=solteq_tand_db_object,
            queue_element_data=queue_element_data,
        )

        # EDI PORTAL
        solteq_app.open_edi_portal()
        time.sleep(5)

        administrative_note = (
            app_context.administrative_note[0].get("Beskrivelse")
            if app_context.administrative_note
            and len(app_context.administrative_note) > 0
            else None
        )

        # Send the documents trough the EDI Portal to the new dentist.
        try:
            ctx = EdiContext(
                extern_clinic_data=app_context.extern_clinic_data,
                queue_element=queue_element_data,
                path_to_files_for_upload=joined_file_paths,
                journal_note=administrative_note,
            )
            receipt_pdf = edi_portal_handler(context=ctx)
            solteq_app.close_edi_portal()
        except Exception as e:
            solteq_app.close_edi_portal()
            raise ProcessError("An error occurred in the EDI Portal process.") from e

        # Check if the receipt PDF was created successfully and upload it to Solteq Tand.
        logger.info("Checking for existing EDI Portal documents.")
        edi_receipt_date_one_month_ago = datetime.datetime.now() - relativedelta(
            months=1
        )
        list_of_documents = solteq_tand_db_object.get_list_of_documents(
            filters={
                "p.cpr": queue_element_data["patient_cpr"],
                "ds.OriginalFilename": f"%EDI Portal - {queue_element_data['patient_name']}%",
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

        # Check if administrative note exists if not create it.
        logger.info("Checking if administrative note exists.")
        journal_note_date_one_month_ago = datetime.datetime.now() - relativedelta(
            months=1
        )
        journal_note = (
            "Administrativt notat 'Udskrivning til frit valg gennemført af robot. "
            "Sendt information til pt. og sendt journal og billedmateriale til "
            "privat tandlæge via EDI-portal. Se dokumentskab. Journal flyttet "
            "til Tandplejen Aarhus'"
        )
        filter_params = {
            "p.cpr": queue_element_data["patient_cpr"],
            "dn.Beskrivelse": f"%{journal_note}%",
            "ds.Dokumenteret": (">=", journal_note_date_one_month_ago),
        }
        result = solteq_tand_db_object.get_list_of_journal_notes(
            filters=filter_params, order_by="ds.Dokumenteret", order_direction="DESC"
        )

        if not result:
            logger.info("Creating administrative note.")
            solteq_app.create_journal_note(
                note_message=journal_note, checkmark_in_complete=True
            )
            logger.info("Administrative note created successfully.")
        else:
            logger.info("Administrative note already exists, skipping creation.")
    except BusinessError as be:
        logger.error("Business error occurred: %s", be)
        raise be
    except Exception as e:
        logger.error("%s", e)
        raise ProcessError("A process error occurred.") from e
    finally:
        close()
