"""Get files for EDI Portal."""

import logging
import os
import pathlib
import shutil
import time

from mbu_rpa_core.exceptions import ProcessError

from helpers import config
from helpers.context_handler import get_context_values

logger = logging.getLogger(__name__)


def _wait_for_document_file(
    path: str, timeout: float = 30.0, interval: float = 1.0
) -> bool:
    """Wait for a document file to appear on disk.

    Solteq writes the journal PDF to the document store after the GUI
    action that creates it has returned, so a document created moments
    earlier can have its database row in place while the file itself is
    not there yet.

    Args:
        path: The document's source path from the database.
        timeout: How long to wait for the file, in seconds.
        interval: Seconds between checks.

    Returns:
        bool: True if the file is there, False if it never appeared.
    """
    deadline = time.monotonic() + timeout

    while True:
        if os.path.exists(path):
            return True

        if time.monotonic() >= deadline:
            return False

        logger.info("Waiting for document file to appear: %s", path)
        time.sleep(interval)


def prepare_edi_portal_documents(solteq_tand_db_object) -> str:
    """
    Prepare documents for EDI Portal:
        - Retrieves the relevant documents.
        - Copies them into a temporary directory.
        - Returns joined file paths ready for EDI upload.
    """

    def get_list_of_documents_for_edi_portal() -> list:
        """Get the latest version of 'Journaludskrift' and other documents for EDI Portal."""
        try:
            document_types = ["Journaludskrift", config.DOCUMENT_TYPE]
            logger.info(
                "Getting documents for EDI Portal for patient with types: %s",
                document_types,
            )
            list_of_documents = solteq_tand_db_object.get_list_of_documents(
                filters={
                    "ds.DocumentType": document_types,
                    "p.cpr": get_context_values("cpr"),
                    "ds.rn": "1",
                    "ds.DocumentStoreStatusId": "1",
                }
            )

            if not list_of_documents:
                logger.error("No documents found for patient.")
                raise ProcessError("No documents found.")

            logger.info("Found %d documents for patient.", len(list_of_documents))

            # Filter to get the latest 'Journaludskrift' based on DocumentCreatedDate
            latest_journal = None
            if "Journaludskrift" in document_types:
                journal_documents = [
                    doc
                    for doc in list_of_documents
                    if doc["DocumentType"] == "Journaludskrift"
                ]
                if journal_documents:
                    latest_journal = max(
                        journal_documents, key=lambda doc: doc["DocumentCreatedDate"]
                    )

            # Include the latest 'Journaludskrift' and other documents
            filtered_documents = [
                doc
                for doc in list_of_documents
                if doc["DocumentType"] != "Journaludskrift"
            ]
            if latest_journal:
                filtered_documents.append(latest_journal)

            # Change filename for Journaludskrift documents to include patient name
            for doc in filtered_documents:
                if doc["DocumentType"] == "Journaludskrift":
                    doc["OriginalFilename"] = (
                        f"Journaludskrift - {get_context_values('patient_name')}.pdf"
                    )

            return filtered_documents
        except ProcessError as e:
            logger.error("Error getting documents for EDI Portal: %s", e)
            raise

    def copy_documents_for_edi_portal(documents: list) -> str:
        """Copy documents for EDI Portal."""
        try:
            logger.info("Copying documents for EDI Portal.")
            temp_dir = os.path.join(
                config.TMP_FOLDER, get_context_values("cpr"), "edi_portal"
            )

            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)

            for document in documents:
                source_path = document["fileSourcePath"]
                destination_path = os.path.join(temp_dir, document["OriginalFilename"])

                if not _wait_for_document_file(source_path):
                    logger.error(
                        "Document file not found on disk: %s (type=%s, created=%s)",
                        source_path,
                        document.get("DocumentType"),
                        document.get("DocumentCreatedDate"),
                    )
                    raise ProcessError(
                        f"Document file not found on disk: {source_path} "
                        f"(type={document.get('DocumentType')}, "
                        f"created={document.get('DocumentCreatedDate')})"
                    )

                shutil.copy2(source_path, destination_path)
                logger.info("Copied %s to %s", source_path, destination_path)

            return temp_dir
        except ProcessError as e:
            logger.error("Error copying documents for EDI Portal: %s", e)
            raise

    # Retrieve and filter the documents
    list_of_documents = get_list_of_documents_for_edi_portal()
    if not list_of_documents:
        logger.error("No documents found for EDI Portal.")
        raise ValueError("No documents found for EDI Portal.")

    # Copy the documents to a temporary folder for the EDI Portal
    path_to_documents = copy_documents_for_edi_portal(list_of_documents)
    files_to_edi_portal = [
        f for f in pathlib.Path(path_to_documents).iterdir() if f.is_file()
    ]
    joined_file_paths = " ".join(f'"{str(f)}"' for f in files_to_edi_portal)
    logger.info("Prepared documents for EDI Portal: %s", joined_file_paths)
    return joined_file_paths
