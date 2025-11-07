"""Check if the medical record document is already created; if not, create it."""

import datetime
import logging
import zoneinfo

from processes.application_handler import get_app

logger = logging.getLogger(__name__)


def check_and_create_medical_record_document(queue_element_data, solteq_tand_db_object):
    """Check if the medical record document is already created; if not, create it."""
    # Get the application instance
    solteq_app = get_app()

    if solteq_app is None:
        raise ValueError("Could not get application instance.")

    logger.info("Checking if the medical record document is already created.")
    local_tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.datetime.now(tz=local_tz)
    one_month_ago = now - datetime.timedelta(days=30)
    document_type = "Journaludskrift"
    list_of_documents_medical_record = solteq_tand_db_object.get_list_of_documents(
        filters={
            "p.cpr": queue_element_data["patient_cpr"],
            "ds.DocumentDescription": "%Printet journal%(delvis kopi)%",
            "ds.DocumentType": document_type,
            "ds.rn": "1",
            "ds.DocumentStoreStatusId": "1",
            "ds.DocumentCreatedDate": (">=", one_month_ago),
        }
    )
    logger.info(
        "Found %d medical record documents.", len(list_of_documents_medical_record)
    )

    if not list_of_documents_medical_record:
        logger.info("Medical record document not found, proceeding to create it.")
        solteq_app.create_digital_printet_journal()
        logger.info("Medical record document created successfully.")
    else:
        logger.info("Medical record document already exists, skipping creation.")
