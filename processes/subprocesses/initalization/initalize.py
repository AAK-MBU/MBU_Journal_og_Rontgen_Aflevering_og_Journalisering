"""Perform initialization checks for the process."""

import logging

from mbu_dev_shared_components.solteqtand import SolteqTandDatabase
from mbu_rpa_core.exceptions import BusinessError, ProcessError

from helpers import config
from helpers.context_handler import get_context_values, set_context_values
from helpers.credential_constants import get_exceptions, get_rpa_constant
from processes.application_handler import get_app

logger = logging.getLogger(__name__)


class InitializationChecks:
    """
    Class to perform initialization checks for the process.
    """

    def __init__(self, queue_element_data) -> None:
        self.queue_element_data = queue_element_data
        self.solteq_tand_db_obj = SolteqTandDatabase(
            get_rpa_constant("solteq_tand_db_connstr")
        )
        self.rpa_db_conn = get_rpa_constant("DbConnectionString")

    def _get_error_message(self, exception_code: str, default: str) -> str:
        """Get the error message from the database based on the exception code."""
        try:
            excp = get_exceptions(self.rpa_db_conn)
            return next(
                (
                    d["message_text"]
                    for d in excp
                    if d["exception_code"] == exception_code
                ),
                default,
            )
        except RuntimeError as e:
            logger.error("Error retrieving exception message: %s", e)
            return default

    def get_primary_clinic_data(self) -> list:
        """Check if primary clinic is set."""
        try:
            filter_params = {
                "p.cpr": get_context_values("cpr"),
            }
            result = self.solteq_tand_db_obj.get_list_of_primary_dental_clinics(
                filters=filter_params
            )

            return result
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            raise

    def check_extern_clinic_data(self) -> list:
        """
        Check if extern dentist phone number is set else raise BusinessError.

        Returns:
            list: A list of extern dentist data.

        Raises:
            BusinessError: If a business rule is broken.
        """
        try:
            filter_params = {
                "p.cpr": get_context_values("cpr"),
            }
            result = self.solteq_tand_db_obj.get_list_of_extern_dentist(
                filters=filter_params
            )

            # Check if extern dentist phone number is set
            logger.info("Checking if phone number is set...")
            if not result[0].get("phoneNumber"):
                message = config.EXTERN_CLINIC_PHONE_NUMBER_NOT_SET_MESSAGE
                raise BusinessError(message)
            logger.info("Phone number is set.")

            return result
        except BusinessError as be:
            logger.error("BusinessError: %s", be)
            raise
        except ProcessError as e:
            logger.error("Application error: %s", e)
            raise

    def get_administrative_note(self) -> list:
        """Check if administrative note is set and returns the note.

        Args:
            None

        Returns:
            list: A list of journal notes.

        Raises:
            BusinessError: If a business rule is broken.
        """
        try:
            filter_params = {
                "p.cpr": get_context_values("cpr"),
                "dn.Beskrivelse": f"%{config.JOURNAL_CONTINUATION_TEXT}%",
            }
            result = self.solteq_tand_db_obj.get_list_of_journal_notes(
                filters=filter_params,
                order_by="ds.Dokumenteret",
                order_direction="DESC",
            )

            # Check if administrative note is set
            logger.info("Checking if administrative note is set...")
            if not result:
                logger.info("Found no administrative note.")

            return result
        except ProcessError as e:
            logger.error("Application error: %s", e)
            raise

    def check_contractor_data(self) -> None:
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

            logger.info("Checking contractor data...")
            if get_context_values("extern_clinic_data") is None:
                raise BusinessError("Extern clinic data is not set.")
            result = solteq_app.edi_portal_check_contractor_id(
                extern_clinic_data=get_context_values("extern_clinic_data")
                if get_context_values("extern_clinic_data")
                else {}
            )

            # Check if contractor id is set
            logger.info("Checking if contractor id is set...")
            if result["rowCount"] == 0:
                message = self._get_error_message("1G", "message_text")
                raise BusinessError(message)
            logger.info("Contractor id is set.")

            # Check if phonenumber is a match
            logger.info("Checking if phonenumber is a match...")
            if result["isPhoneNumberMatch"] is False:
                message = self._get_error_message("1H", "message_text")
                raise BusinessError(message)
            logger.info("Phonenumber matched.")
            solteq_app.close_edi_portal()
        except BusinessError as be:
            solteq_app.close_edi_portal()
            logger.error("BusinessError: %s", be)
            raise
        except ProcessError as error:
            solteq_app.close_edi_portal()
            logger.error("Error checking contractor data: %s", error)
            raise


def initalization_checks_and_get_data(queue_element_data) -> None:
    """
    Perform initialization checks for the process.
    - Get primary clinic data.
    - Check if extern dentist phone number is set and get extern clinic data.
    - Get administrative note.
    - Check if contractor phone number from EDI-Portal matches the one in Solteq Tand.

    Args:
        orchestrator_connection: A connection to OpenOrchestrator.

    Raises:
        BusinessError: If a business rule is broken.
    """
    solteq_tand_db_conn = get_rpa_constant("solteq_tand_db_connstr")
    if not solteq_tand_db_conn:
        raise ValueError("solteq_tand_db_connstr is not set.")

    rpa_db_conn = get_rpa_constant("rpa_db_connstr")
    if not rpa_db_conn:
        raise ValueError("rpa_db_connstr is not set.")

    # Creates an instance of the initializationChecks class
    init_checks_obj = InitializationChecks(
        queue_element_data=queue_element_data,
    )

    logger.info(
        "Performing initialization checks, getting primary clinic data and administrative note..."
    )

    # Get primary clinic data
    set_context_values(
        primary_clinic_and_patient_data=init_checks_obj.get_primary_clinic_data()
    )

    # Check if extern dentist phone number is set and get extern clinic data
    set_context_values(extern_clinic_data=init_checks_obj.check_extern_clinic_data())

    # Get administrative note
    set_context_values(administrative_note=init_checks_obj.get_administrative_note())
    administrative_note = get_context_values("administrative_note")
    if administrative_note:
        description = administrative_note[0].get("Beskrivelse")
    set_context_values(
        administrative_note_description=description if administrative_note else []
    )

    # Check if contractor phone number from EDI-Portal matches the one in Solteq Tand
    init_checks_obj.check_contractor_data()

    logger.info("Initialization checks completed.")
