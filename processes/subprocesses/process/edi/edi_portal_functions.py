"""
This module contains functions to interact with the EDI portal.
These functions should be moved to mbu_dev_shared_components/solteqtand/application/edi_portal.py
"""

import logging
import re
import shutil
import subprocess
import time
import zoneinfo
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyodbc
import uiautomation as auto

from helpers import config

logger = logging.getLogger(__name__)


def _kill_adobe() -> None:
    """Force-kills any running Adobe Acrobat/Reader processes."""
    subprocess.call(["taskkill", "/F", "/IM", "Acrobat.exe"], stderr=subprocess.DEVNULL)
    subprocess.call(
        ["taskkill", "/F", "/IM", "AcroRd32.exe"], stderr=subprocess.DEVNULL
    )


def wait_for_control(
    control_type, search_params, search_depth=1, timeout=30, retry_interval=0.5
):
    """
    Waits for a given control type to become available with the specified search parameters.

    Args:
        control_type: The type of control, e.g., auto.WindowControl, auto.ButtonControl, etc.
        search_params (dict): Search parameters used to identify the control.
                            The keys must match the properties used in the control type, e.g., 'AutomationId', 'Name'.
        search_depth (int): How deep to search in the user interface.
        timeout (int): Maximum time to wait for the control, in seconds.
        retry_interval (float): Time to wait between retries, in seconds.

    Returns:
        Control: The control object if found, otherwise raises TimeoutError.

    Raises:
        TimeoutError: If the control is not found within the timeout period.
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            control = control_type(searchDepth=search_depth, **search_params)
            if control.Exists(0, 0):
                return control
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error while searching for control: %s", e)

        time.sleep(retry_interval)

    logger.warning("Timeout reached while searching for control: %s", search_params)
    raise TimeoutError(
        f"Control with parameters {search_params} was not found within the {timeout} second timeout."
    )


def wait_for_control_to_disappear(
    control_type, search_params, search_depth=1, timeout=30
):
    """
    Waits for a given control type to disappear with the specified search parameters.

    Args:
        control_type: The type of control, e.g., auto.WindowControl, auto.ButtonControl, etc.
        search_params (dict): Search parameters used to identify the control.
                            The keys must match the properties used in the control type, e.g., 'AutomationId', 'Name'.
        search_depth (int): How deep to search in the user interface.
        timeout (int): How long to wait, in seconds.

    Returns:
        bool: True if the control disappeared within the timeout period, otherwise False.
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            control = control_type(searchDepth=search_depth, **search_params)
            if not control.Exists(0, 0):
                return True
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error while searching for control: %s", e)

        time.sleep(0.5)

    raise TimeoutError(
        f"Control with parameters {search_params} did not disappear within the timeout period."
    )


def edi_portal_check_contractor_id(
    extern_clinic_data: dict, sleep_time: int = 5
) -> dict:
    """
    Checks if the contractor ID is valid in the EDI portal.

    Args:
        extern_clinic_data (dict): A dictionary containing the contractor ID and phone number.
        sleep_time (int): Time to wait after clicking the next button.

    Returns:
        dict: A dictionary containing the row count and whether the phone number matches.
    """
    try:
        # Handle Hasle Torv Clinic special case
        contractor_id = None
        clinic_phone_number = None

        # Handle Hasle Torv Clinic special case
        if (
            extern_clinic_data[0]["contractorId"] == "477052"
            or extern_clinic_data[0]["contractorId"] == "470678"
        ):
            contractor_id = "485055"
            clinic_phone_number = "86135240"
        else:
            contractor_id = (
                extern_clinic_data[0]["contractorId"]
                if extern_clinic_data[0]["contractorId"]
                else None
            )
            clinic_phone_number = (
                extern_clinic_data[0]["phoneNumber"]
                if extern_clinic_data[0]["phoneNumber"]
                else None
            )

        edi_portal_click_next_button(sleep_time=2)

        class_options = [
            "form-control filter_search",
            "form-control filter_search valid",
        ]

        for class_name in class_options:
            try:
                search_box = wait_for_control(
                    auto.EditControl,
                    {"ClassName": class_name},
                    search_depth=50,
                    timeout=5,
                )
            except TimeoutError:
                continue
            if search_box:
                break

        search_box.SetFocus()
        search_box_value_pattern = search_box.GetPattern(auto.PatternId.ValuePattern)
        search_box_value_pattern.SetValue(
            contractor_id if contractor_id else clinic_phone_number
        )
        search_box.SendKeys("{ENTER}")

        time.sleep(sleep_time)

        table_dentists = wait_for_control(
            auto.TableControl,
            {"AutomationId": "dtRecipients"},
            search_depth=50,
        )
        grid_pattern = table_dentists.GetPattern(auto.PatternId.GridPattern)
        row_count = grid_pattern.RowCount

        is_phone_number_match = False

        if grid_pattern.GetItem(1, 0).Name == "Ingen data i tabellen":
            return {"rowCount": 0, "isPhoneNumberMatch": False}

        if row_count > 0:
            for row in range(row_count):
                phone_number = grid_pattern.GetItem(row, 5).Name
                if phone_number == clinic_phone_number:
                    is_phone_number_match = True
                    break
        return {"rowCount": row_count, "isPhoneNumberMatch": is_phone_number_match}
    except Exception as e:
        logger.error("Error while checking contractor ID in EDI Portal: %s", e)
        raise


def edi_portal_click_next_button(sleep_time: int) -> None:
    """
    Clicks the next button in the EDI portal.

    Args:
        sleep_time (int): Time to wait after clicking the next button.
    """
    try:
        edge_window = wait_for_control(
            auto.WindowControl, {"ClassName": "Chrome_WidgetWin_1"}, search_depth=3
        )

        edge_window.SetFocus()

        root_web_area = wait_for_control(
            edge_window.DocumentControl,
            {"AutomationId": "RootWebArea"},
            search_depth=30,
        )

        try:
            next_button = wait_for_control(
                root_web_area.ButtonControl,
                {"Name": "Næste"},
                search_depth=50,
                timeout=5,
            )
        except TimeoutError:
            next_button = None

        if not next_button:
            try:
                next_button = wait_for_control(
                    root_web_area.ButtonControl,
                    {"AutomationId": "patientInformationNextButton"},
                    search_depth=50,
                    timeout=5,
                )
            except TimeoutError:
                next_button = None

        if not next_button:
            logger.error("Next button not found in EDI Portal")
            raise RuntimeError("Next button not found in EDI Portal")
        next_button.Click(simulateMove=False, waitTime=0)
        time.sleep(sleep_time)
    except Exception as e:
        logger.error("Error while clicking next button in EDI Portal: %s", e)
        raise


def edi_portal_lookup_contractor_id(extern_clinic_data: dict) -> None:
    """
    Looks up the contractor ID in the EDI portal.

    Args:
        extern_clinic_data (dict): A dictionary containing the contractor ID and phone number.
    """
    try:
        contractor_id = None
        clinic_phone_number = None

        # Handle Hasle Torv Clinic special case
        if (
            extern_clinic_data[0]["contractorId"] == "477052"
            or extern_clinic_data[0]["contractorId"] == "470678"
        ):
            contractor_id = "485055"
            clinic_phone_number = "86135240"
        else:
            contractor_id = (
                extern_clinic_data[0]["contractorId"]
                if extern_clinic_data[0]["contractorId"]
                else None
            )
            clinic_phone_number = (
                extern_clinic_data[0]["phoneNumber"]
                if extern_clinic_data[0]["phoneNumber"]
                else None
            )

        class_options = [
            "form-control filter_search",
            "form-control filter_search valid",
        ]

        for class_name in class_options:
            try:
                search_box = wait_for_control(
                    auto.EditControl,
                    {"ClassName": class_name},
                    search_depth=50,
                    timeout=5,
                )
            except TimeoutError:
                continue
            if search_box:
                break

        search_box.SetFocus()
        search_box_value_pattern = search_box.GetPattern(auto.PatternId.ValuePattern)
        search_box_value_pattern.SetValue(
            contractor_id if contractor_id else clinic_phone_number
        )
        search_box.SendKeys("{ENTER}")
        time.sleep(3)
    except Exception as e:
        logger.error("Error while looking up contractor ID in EDI Portal: %s", e)
        raise


def edi_portal_choose_receiver(extern_clinic_data: dict) -> None:
    """
    Chooses the receiver in the EDI portal based on a matching phone number.

    Args:
        extern_clinic_data (dict): A dictionary containing the contractor ID and phone number.
    """
    try:
        if (
            extern_clinic_data[0]["contractorId"] == "477052"
            or extern_clinic_data[0]["contractorId"] == "470678"
        ):
            clinic_phone_number = "86135240"
        else:
            clinic_phone_number = extern_clinic_data[0]["phoneNumber"]

        table_dentists = wait_for_control(
            auto.TableControl,
            {"AutomationId": "dtRecipients"},
            search_depth=50,
        )
        grid_pattern = table_dentists.GetPattern(auto.PatternId.GridPattern)
        row_count = grid_pattern.RowCount

        if row_count > 0:
            for row in range(row_count):
                phone_number = grid_pattern.GetItem(row, 5).Name
                if phone_number == clinic_phone_number:
                    grid_pattern.GetItem(row, 0).Click(simulateMove=False, waitTime=0)
                    break
    except Exception as e:
        logger.error("Error while choosing receiver in EDI Portal: %s", e)
        raise


def _subject_build(subject: str, contractor_id: str) -> str:
    """Build the EDI portal subject line.

    Appends a clinic-specific suffix based on the contractor ID and
    verifies the result fits the EDI portal's character limit.

    Args:
        subject: The base subject text.
        contractor_id: Contractor ID used to select the clinic suffix.

    Returns:
        The final subject line.

    Raises:
        ValueError: If the subject or contractor ID is missing, or if the
            final subject exceeds 66 characters.
    """

    if not subject:
        logger.error("Subject is missing.")
        raise ValueError("Subject is missing.")

    if not contractor_id:
        logger.error("Contractor ID is missing.")
        raise ValueError("Contractor ID is missing.")

    if contractor_id == "477052":
        subject = subject + " på Tandklinikken Hasle Torv"
    elif contractor_id == "470678":
        subject = subject + " på Tandklinikken Brobjergparken"

    MAX_SUBJECT_LENGTH = 66

    if len(subject) > MAX_SUBJECT_LENGTH:
        logger.error("Subject exceeds 66 characters: %d", len(subject))
        raise ValueError(f"Subject exceeds 66 characters: {len(subject)}")

    return subject


def edi_portal_add_content(
    edi_portal_content: dict[str, Any],
    extern_clinic_data: list[dict[str, str]],
    journal_continuation_text: str | None = None,
) -> None:
    """
    Adds content to the EDI portal based on the provided queue element and content template.

    Args:
        edi_portal_content:
            Content template containing the keys "subject" and "body".
        extern_clinic_data:
            External clinic data. The first item must contain "contractorId".
        journal_continuation_text:
            Optional text used to replace the @dentalPlan placeholder.

    Raises:
        ValueError:
            If required content or clinic data is missing.
    """

    subject_template = edi_portal_content["subject"]
    if not subject_template:
        logger.error("Subject is required.")
        raise ValueError("Subject is required.")

    body = edi_portal_content["body"]
    if not body:
        logger.error("Body is required.")
        raise ValueError("Body is required.")

    if not extern_clinic_data:
        logger.error("External clinic data is required.")
        raise ValueError("External clinic data is required.")

    contractor_id = extern_clinic_data[0]["contractorId"]
    if not contractor_id:
        logger.error("ContractorId is required.")
        raise ValueError("ContractorId is required.")

    subject = _subject_build(
        subject=subject_template,
        contractor_id=contractor_id,
    )

    if journal_continuation_text:
        prefix = config.JOURNAL_CONTINUATION_TEXT

        if prefix:
            journal_continuation_text = journal_continuation_text.removeprefix(prefix)

        journal_continuation_text = journal_continuation_text.strip()

        body = body.replace(
            "@dentalPlan",
            journal_continuation_text,
        )
    else:
        body = re.sub(
            r"^[ \t]*@dentalPlan[ \t]*(?:\r?\n)?",
            "",
            body,
            flags=re.MULTILINE,
        )

    logger.info(
        "EDI portal content prepared. Journal continuation provided: %s",
        bool(journal_continuation_text),
    )
    logger.info("body: %s", body)
    logger.info("BREAKPOINT")

    try:
        root_web_area = wait_for_control(
            auto.DocumentControl, {"AutomationId": "RootWebArea"}, search_depth=30
        )

        group = wait_for_control(
            root_web_area.GroupControl,
            {"AutomationId": "formId"},
            search_depth=50,
        )

        subject_field = wait_for_control(
            group.EditControl,
            {"AutomationId": "ContentTitleInput"},
            search_depth=50,
        )
        subject_field_value_pattern = subject_field.GetPattern(
            auto.PatternId.ValuePattern
        )
        subject_field_value_pattern.SetValue(subject)

        body_field = wait_for_control(
            group.EditControl, {"AutomationId": "ContentInput"}, search_depth=50
        )
        body_field_value_pattern = body_field.GetPattern(auto.PatternId.ValuePattern)
        body_field_value_pattern.SetValue(body)

    except Exception as e:
        logger.error("Error while adding content in EDI Portal: %s", e)
        raise


def edi_portal_upload_files(path_to_files: str) -> None:
    """
    Uploads files to the EDI portal.
    """
    upload_field = wait_for_control(
        auto.GroupControl, {"AutomationId": "createNewUpload"}, search_depth=50
    )
    upload_field.Click(simulateMove=False, waitTime=0)

    upload_dialog = wait_for_control(
        auto.WindowControl, {"Name": "Åbn"}, search_depth=5
    )

    upload_dialog_path_field = wait_for_control(
        upload_dialog.EditControl, {"ClassName": "Edit"}, search_depth=5
    )
    upload_dialog_value_pattern = upload_dialog_path_field.GetPattern(
        auto.PatternId.ValuePattern
    )
    upload_dialog_value_pattern.SetValue(path_to_files)
    upload_dialog.SendKeys("{ENTER}")

    root_web_area = wait_for_control(
        auto.DocumentControl, {"AutomationId": "RootWebArea"}, search_depth=30
    )

    element_gone = False
    timeout = 180  # Set a timeout for the upload progress check
    while not element_gone and timeout > 0:
        try:
            upload_progress = wait_for_control(
                root_web_area.TextControl,
                {
                    "Name": "En eller flere filer er under behandling. Du kan fortsætte til næste trin, når arbejdet er færdigt."
                },
                search_depth=20,
                timeout=5,
            )
            if upload_progress:
                time.sleep(5)
                timeout -= 5
            else:
                element_gone = True
        except TimeoutError:
            element_gone = True


def edi_portal_choose_priority(priority: str = "Rutine") -> None:
    """
    Chooses the priority in the EDI portal.

    Args:
        priority (str): The priority to be set.
    """
    try:
        priority_field = wait_for_control(
            auto.RadioButtonControl,
            {"Name": f"{priority}"},
            search_depth=21,
        )
        priority_field.Click(simulateMove=False, waitTime=0)
    except Exception as e:
        logger.error("Error while choosing priority in EDI Portal: %s", e)
        raise


def edi_portal_send_message() -> None:
    """
    Sends a message in the EDI portal.
    """
    try:
        root_web_area = wait_for_control(
            auto.DocumentControl, {"AutomationId": "RootWebArea"}, search_depth=30
        )

        send_message_button = wait_for_control(
            root_web_area.ButtonControl,
            {"AutomationId": "submitButton"},
            search_depth=4,
        )
        send_message_button.Click(simulateMove=False, waitTime=0)
        logger.info("Message sent in EDI Portal.")
    except Exception as e:
        logger.error("Error while sending message in EDI Portal: %s", e)
        raise


def _find_latest_matching_message(
    grid_pattern, row_count: int, subject: str
) -> int | None:
    """
    Finds the latest matching message row based on the subject.

    Args:
        grid_pattern: The grid pattern of the table.
        row_count (int): The number of rows in the table.
        subject (str): The subject to match.

    Returns:
        int | None: The row index of the latest matching message, or None if not found.
    """

    def _parse_date(date_str: str) -> datetime | None:
        """Parse date from format like '11-09-2025 13:28'"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d-%m-%Y %H:%M").replace(
                tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
            )
        except ValueError:
            return None

    latest_matching_row = None
    latest_date = None

    if row_count <= 0:
        return None

    for row in range(1, row_count):
        message = grid_pattern.GetItem(row, 6).Name or ""
        date_str = grid_pattern.GetItem(row, 2).Name or ""

        if subject != message:
            continue

        parsed_date = _parse_date(date_str)

        if parsed_date is None:
            continue

        if latest_date is None or parsed_date > latest_date:
            latest_matching_row = row
            latest_date = parsed_date

    return latest_matching_row


def _get_menu_popup(root_web_area) -> auto.ListControl:
    """
    Helper function to get the menu popup control.

    Args:
        root_web_area: The root web area control.

    Returns:
        auto.ListControl: The menu popup control.

    Raises:
        TimeoutError: If the menu popup is not found.
    """
    class_names = ["dropdown-menu show", "dropdown-menu"]

    for class_name in class_names:
        try:
            menu_popup = wait_for_control(
                root_web_area.ListControl,
                {"ClassName": class_name},
                search_depth=50,
                timeout=15,
            )
            if menu_popup:
                return menu_popup
        except TimeoutError:
            continue

    raise TimeoutError("Could not find dropdown menu with any method")


def edi_portal_get_journal_sent_receip(subject: str) -> str:
    """
    Checks if the message was sent successfully in the EDI portal,
    and downloads the receipt.

    Args:
        subject (str): The subject of the message to check.

    Returns:
        str: The path to the downloaded receipt PDF.

    Raises:
        RuntimeError: If the message was not sent successfully.
        TimeoutError: If the receipt download does not complete within 60 seconds.
        FileNotFoundError: If no receipt PDF is found after the download.
    """
    try:
        table_post_messages = wait_for_control(
            auto.TableControl,
            {"AutomationId": "dtSent"},
            search_depth=50,
        )
        grid_pattern = table_post_messages.GetPattern(auto.PatternId.GridPattern)
        row_count = grid_pattern.RowCount

        latest_matching_row = None
        latest_date = None

        def _parse_date(date_str: str) -> datetime | None:
            """Parse a Danish portal date such as '11-09-2025 13:28'."""
            if not date_str:
                return None

            try:
                return datetime.strptime(
                    date_str,
                    "%d-%m-%Y %H:%M",
                ).replace(tzinfo=ZoneInfo("Europe/Copenhagen"))
            except ValueError:
                return None

        if row_count > 0:
            for row in range(1, row_count):
                message = grid_pattern.GetItem(row, 6).Name or ""
                date_str = grid_pattern.GetItem(row, 2).Name or ""

                if subject == message:
                    parsed_date = _parse_date(date_str)

                    if parsed_date is not None and (
                        latest_date is None or parsed_date > latest_date
                    ):
                        latest_matching_row = row
                        latest_date = parsed_date

        if latest_matching_row is None:
            logger.error("Message not sent.")
            raise RuntimeError("Message not sent.")

        latest_row_cell = grid_pattern.GetItem(latest_matching_row, 0)
        latest_row_parent = latest_row_cell.GetParentControl()

        url_field = wait_for_control(
            auto.EditControl,
            {"Name": "Adresse- og søgelinje"},
            search_depth=25,
        )
        url_field_value_pattern = url_field.GetPattern(auto.PatternId.ValuePattern)
        url_field_value_pattern.SetValue(
            "https://ediportalen.dk/Messages/"
            "DownloadMessageDetailPdf"
            f"?id={latest_row_parent.AutomationId}&isInbox=False"
        )
        url_field.SendKeys("{ENTER}")

        time.sleep(5)

        download_path = Path.home() / "Downloads"
        timeout = 60
        deadline = time.time() + timeout

        while next(download_path.glob("Meddelelse*.crdownload"), None):
            if time.time() > deadline:
                logger.error("Download did not complete within 60 seconds.")
                raise TimeoutError("Download did not complete within 60 seconds.")

            time.sleep(1)

        receipts = list(download_path.glob("Meddelelse*.pdf"))
        if not receipts:
            logger.error("No matching receipt PDF found after download.")
            raise FileNotFoundError("No matching receipt PDF found after download.")

        receipt = max(receipts, key=lambda path: path.stat().st_mtime)

        _kill_adobe()
        time.sleep(2)

        return str(receipt)

    except Exception as e:
        logger.error("Error while downloading the receipt from EDI Portal: %s", e)
        raise


def rename_file(
    file_path: str,
    new_name: str,
    extension: str,
    retries: int = 10,
    retry_interval: float = 3.0,
) -> str:
    """
    Renames a file and returns its new path.

    Waits briefly before attempting the rename to allow any application
    (e.g. Adobe Acrobat) to release its file handle, then uses shutil.move
    to avoid triggering Windows shell notifications that can cause the file
    to be opened automatically.

    Args:
        file_path      (str):   Full path to the file to rename.
        new_name       (str):   New filename without extension.
        extension      (str):   New extension (e.g. '.pdf').
        retries        (int):   Number of times to retry if the file is locked.
        retry_interval (float): Seconds to wait between retries.

    Returns:
        str: Absolute path to the renamed file.

    Raises:
        FileNotFoundError: If the source file does not exist.
        OSError:           If the rename operation fails after all retries.
    """
    path = Path(file_path)

    if not path.exists():
        logger.error("File not found: %s", file_path)
        raise FileNotFoundError(f"File not found: {file_path}")

    new_file_path = path.parent / f"{new_name}{extension}"

    _kill_adobe()
    time.sleep(3)

    last_error: Exception = OSError("Unknown error during rename.")
    for attempt in range(retries):
        try:
            shutil.move(str(path), str(new_file_path))
            time.sleep(5)
            _kill_adobe()
            return str(new_file_path)
        except PermissionError as e:
            last_error = e
            if attempt < retries - 1:
                logger.warning(
                    "File is locked, retrying in %ss... (attempt %s/%s)",
                    retry_interval,
                    attempt + 1,
                    retries,
                )
                _kill_adobe()
                time.sleep(retry_interval)

    raise OSError(
        f"Could not rename '{file_path}' after {retries} attempts: {last_error}"
    ) from last_error


def get_constants(conn_string: str, name: str) -> list:
    """Retrieve the constants from the database."""
    try:
        query = """
            SELECT
                *
            FROM
                [RPA].[rpa].[Constants]
            WHERE
                [name] = ?
        """
        params = (name,)

        with pyodbc.connect(conn_string) as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description]
            constant_value = [
                dict(zip(columns, row, strict=True)) for row in cursor.fetchall()
            ]

        return constant_value

    except pyodbc.Error as e:
        logger.error("Database error: %s", e)
        raise
    except Exception as e:
        logger.error("Error retrieving constants: %s", e)
        raise


def edi_portal_is_patient_data_sent(subject: str) -> bool:
    """
    Checks if the patient data has been sent in the EDI portal.

    Returns:
        bool: True if the patient data has been sent, False otherwise.
    """

    def _parse_date(date_str: str) -> datetime | None:
        """Parse date from format like '11-09-2025 13:28'"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d-%m-%Y %H:%M").replace(
                tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
            )
        except ValueError:
            logger.error("Error parsing date: %s", date_str)
            return None

    try:
        url_field = wait_for_control(
            auto.EditControl, {"Name": "Adresse- og søgelinje"}, search_depth=25
        )
        url_field_value_pattern = url_field.GetPattern(auto.PatternId.ValuePattern)
        url_field_value_pattern.SetValue("https://ediportalen.dk/Messages/Sent")
        url_field.SendKeys("{ENTER}")

        time.sleep(5)

        test = wait_for_control(
            auto.WindowControl, {"ClassName": "Chrome_WidgetWin_1"}, search_depth=3
        )

        test.SetFocus()
        next_test = wait_for_control(
            test.PaneControl, {"ClassName": "BrowserRootView"}, search_depth=4
        )

        table_post_messages = wait_for_control(
            next_test.TableControl,
            {"AutomationId": "dtSent"},
            search_depth=50,  # changed from table_id1
        )
        grid_pattern = table_post_messages.GetPattern(auto.PatternId.GridPattern)
        row_count = grid_pattern.RowCount
        success_message = False

        # Define one month ago here
        local_tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
        now = datetime.now(tz=local_tz)
        one_month_ago = now - timedelta(days=30)

        if row_count > 0:
            for row in range(1, row_count):
                message = grid_pattern.GetItem(row, 6).Name or ""
                date_str = grid_pattern.GetItem(row, 2).Name or ""

                # Check if message contains the target text
                if subject not in message:
                    continue

                # Parse and check if date is older than 1 month
                parsed_date = _parse_date(date_str)
                if parsed_date is None:
                    continue

                # Both conditions must be true: message contains subject AND date is older than 1 month
                if parsed_date >= one_month_ago:
                    success_message = True
                    break

        return bool(success_message)

    except TimeoutError:
        return False
    except Exception as e:
        logger.error(
            "Error while checking if patient data is sent in EDI Portal: %s", e
        )
        raise


def edi_portal_go_to_send_journal() -> None:
    """
    Navigates to the 'Opret ny journalforsendelse' section in the EDI portal.
    """
    try:
        url_field = wait_for_control(
            auto.EditControl, {"Name": "Adresse- og søgelinje"}, search_depth=25
        )
        url_field_value_pattern = url_field.GetPattern(auto.PatternId.ValuePattern)
        url_field_value_pattern.SetValue("https://ediportalen.dk/Journal/Create")
        url_field.SendKeys("{ENTER}")
    except Exception as e:
        logger.error("Error while navigating to 'Send journal' in EDI Portal: %s", e)
        raise
