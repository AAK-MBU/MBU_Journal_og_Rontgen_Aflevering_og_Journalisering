"""This module provides the EDI portal handler for processing EDI-related tasks."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from helpers.credential_constants import get_rpa_constant
from processes.subprocesses.process.edi import (
    edi_portal_functions as edifuncs,
)

logger = logging.getLogger(__name__)


# Context object to hold all inputs and intermediate state
@dataclass
class EdiContext:
    """
    EdiContext is a context object that holds all inputs and intermediate state
    required for processing in the EDI portal handler.

    Attributes:
        extern_clinic_data (list[Dict[str, Any]]): External clinic data used in processing.
        queue_element (Dict[str, Any]): Queue element containing relevant information.
        journal_note (str): Note to be added to the journal.
        path_to_files_for_upload (str): Path to the files that need to be uploaded.
        subject (str): Subject of the context. Defaults to an empty string.
        receipt_path (Optional[str]): Path to the receipt file. Defaults to None.
    """

    extern_clinic_data: list[dict[str, Any]]
    queue_element: dict[str, Any]
    path_to_files_for_upload: str
    subject: str = ""
    journal_note: str | None = None
    value_data: dict[str, Any] | None = None
    receipt_path: str | None = None


# A pipeline step is any callable that receives the context and operates on it
Step = Callable[[EdiContext], bool | None]


def edi_portal_handler(context: EdiContext) -> str | None:
    """
    Executes the end-to-end EDI portal workflow using a Context object.

    Steps are defined as functions (or lambdas) that take the shared context,
    enabling cleaner signatures and centralized state management.

    Args:
        context (EdiContext):
            Holds all input parameters and manages intermediate state such as
            computed subject lines and receipt paths.

    Returns:
        Optional[str]:
            Path to the renamed PDF receipt, or None on failure.
    """
    constant = get_rpa_constant("udskrivning_edi_portal_content")
    if not constant:
        logger.error(
            "Constant 'udskrivning_edi_portal_content' not found in the database."
        )
        raise RuntimeError(
            "Constant 'udskrivning_edi_portal_content' not found in the database."
        )

    context.value_data = json.loads(constant) if isinstance(constant, str) else constant

    if not context.value_data or "edi_portal_content" not in context.value_data:
        logger.error("Invalid or missing 'edi_portal_content' data in constant.")
        raise RuntimeError("Invalid or missing 'edi_portal_content' data in constant.")

    patient_name = context.queue_element.get("patient_name")
    base_subject = context.value_data["edi_portal_content"]["subject"]

    if context.extern_clinic_data[0]["contractorId"] == "477052":
        subject = base_subject + " på Tandklinikken Hasle Torv " + patient_name
    elif context.extern_clinic_data[0]["contractorId"] == "470678":
        subject = base_subject + " på Tandklinikken Brobjergparken " + patient_name
    else:
        subject = base_subject + " " + patient_name

    context.subject = subject

    # Define the ordered list of pipeline steps
    pipeline: list[Step] = [
        # Navigation
        lambda ctx: edifuncs.edi_portal_is_patient_data_sent(subject=ctx.subject),
        lambda _: edifuncs.edi_portal_go_to_send_journal(),
        lambda _: edifuncs.edi_portal_click_next_button(sleep_time=2),
        # Contractor lookup and selection
        lambda ctx: edifuncs.edi_portal_lookup_contractor_id(
            extern_clinic_data=ctx.extern_clinic_data
        ),
        lambda ctx: edifuncs.edi_portal_choose_receiver(
            extern_clinic_data=ctx.extern_clinic_data
        ),
        lambda _: edifuncs.edi_portal_click_next_button(sleep_time=2),
        # Add journal content
        lambda ctx: edifuncs.edi_portal_add_content(
            queue_element=ctx.queue_element,
            edi_portal_content=ctx.value_data["edi_portal_content"],  # type: ignore
            journal_continuation_text=ctx.journal_note,
            extern_clinic_data=ctx.extern_clinic_data,
        ),
        lambda _: edifuncs.edi_portal_click_next_button(sleep_time=2),
        # File upload
        lambda ctx: edifuncs.edi_portal_upload_files(
            path_to_files=ctx.path_to_files_for_upload
        ),
        lambda _: edifuncs.edi_portal_click_next_button(sleep_time=2),
        # Priority & send
        # lambda ctx: edifuncs.edi_portal_choose_priority(),
        lambda _: edifuncs.edi_portal_click_next_button(sleep_time=2),
        lambda _: edifuncs.edi_portal_send_message(),
        # # Retrieve the sent receipt
        lambda ctx: setattr(
            ctx,
            "receipt_path",
            edifuncs.edi_portal_get_journal_sent_receip(subject=ctx.subject),
        ),
        # Rename the receipt on disk
        lambda ctx: setattr(
            ctx,
            "receipt_path",
            edifuncs.rename_file(
                file_path=ctx.receipt_path,  # type: ignore
                new_name=f"EDI Portal - {patient_name}",
                extension=".pdf",
            ),
        ),
    ]

    # Execute each step in sequence
    skip_steps = False
    for step in pipeline[:-2]:  # Exclude the last two steps from conditional skipping
        try:
            if skip_steps:
                logger.info("Skipping step due to earlier condition.")
                continue

            if step(context):
                logger.info(
                    "Step returned True, skipping remaining steps until the last two."
                )
                skip_steps = True
            else:
                logger.info("Step returned False, continuing.")
        except Exception as e:
            logger.error(
                "Error occurred in step %s: %s",
                step.__name__ if hasattr(step, "__name__") else str(step),
                str(e),
            )
            raise RuntimeError(
                f"Step {step.__name__ if hasattr(step, '__name__') else step} failed: {e}"
            ) from e

    # Always run the last two steps
    for step in pipeline[-2:]:
        try:
            step(context)
        except Exception as e:
            logger.error(
                "Error occurred in step %s: %s",
                step.__name__ if hasattr(step, "__name__") else str(step),
                str(e),
            )
            raise RuntimeError(
                f"Step {step.__name__ if hasattr(step, '__name__') else step} failed: {e}"
            ) from e

    return context.receipt_path
