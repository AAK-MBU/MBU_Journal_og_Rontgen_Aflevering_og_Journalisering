"""
This module contains functions to interact with the EDI portal.
These functions should be moved to mbu_dev_shared_components/solteqtand/application/edi_portal.py
"""

import locale
import logging
import re
import time
import zoneinfo
from datetime import datetime, timedelta
from pathlib import Path

import pyodbc
import uiautomation as auto

from helpers import config

logger = logging.getLogger(__name__)


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
                phone_number = grid_pattern.GetItem(row, 4).Name
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
                phone_number = grid_pattern.GetItem(row, 4).Name
                if phone_number == clinic_phone_number:
                    grid_pattern.GetItem(row, 0).Click(simulateMove=False, waitTime=0)
                    break
    except Exception as e:
        logger.error("Error while choosing receiver in EDI Portal: %s", e)
        raise


def edi_portal_add_content(
    queue_element: dict,
    edi_portal_content: dict,
    extern_clinic_data: dict,
    journal_continuation_text: str | None = None,
) -> None:
    """
    Adds content to the EDI portal based on the provided queue element and content template.

    Args:
        queue_element (dict): The queue element containing data for the content.
        edi_portal_content (dict): The content template for the EDI portal.
        journal_continuation_text (str | None): Additional text to be added to the content.
    """

    def _get_formatted_date(data) -> str:
        """
        Helper function to format the date from the data dictionary.
        Args:
            data (dict): The data dictionary containing the date information.
        Returns:
            str: The formatted date string or an error message.
        """
        try:
            locale.setlocale(locale.LC_TIME, "da_DK.UTF-8")
        except locale.Error:
            return "Error setting locale to Danish"

        if data.get("ukendt_dato") is True:
            return "Ukendt"

        try:
            date_str = data["dateOfExamination"]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
            )
            return date_obj.strftime("%B %Y").capitalize()
        except (ValueError, KeyError):
            logger.error("Error parsing date: %s", date_str)
            return "Error parsing date"

    subject = edi_portal_content["subject"]

    if not subject:
        logger.error("Subject is required.")
        raise ValueError("Subject is required.")

    if extern_clinic_data[0]["contractorId"] == "477052":
        subject = subject + " på Tandklinikken Hasle Torv "
    elif extern_clinic_data[0]["contractorId"] == "470678":
        subject = subject + " på Tandklinikken Brobjergparken "

    # Truncate subject to 66 characters to fit EDI portal limitations
    subject = subject[:66]

    body = edi_portal_content["body"]
    if not body:
        logger.error("Body is required.")
        raise ValueError("Body is required.")

    dental_plan = queue_element.get("tandplejeplan")

    if journal_continuation_text:
        if config.JOURNAL_CONTINUATION_TEXT in journal_continuation_text:
            journal_continuation_text = journal_continuation_text.replace(
                config.JOURNAL_CONTINUATION_TEXT, ""
            )
        elif config.JOURNAL_CONTINUATION_REPLACEMENT_TEXT in journal_continuation_text:
            journal_continuation_text = journal_continuation_text.replace(
                config.JOURNAL_CONTINUATION_REPLACEMENT_TEXT,
                "",
            )

    if dental_plan:
        body = re.sub(
            r"@dentalPlan",
            f"{journal_continuation_text}",
            body,
        )
    else:
        body = re.sub(r"\n\s*@dentalPlan\s", "\n", body)

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


def _find_latest_sent_row(grid_pattern, row_count: int, subject: str) -> int | None:
    """
    Scans the sent messages table and returns the row index of the most
    recent message whose subject exactly matches *subject*.

    Args:
        grid_pattern: The grid pattern of the sent messages table.
        row_count (int): The number of rows in the table.
        subject (str): The subject to match.

    Returns:
        int | None: The row index of the latest matching message, or None if not found.
    """

    def _parse_date(date_str: str) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d-%m-%Y %H:%M").replace(
                tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
            )
        except ValueError:
            return None

    latest_row = None
    latest_date = None

    for row in range(1, row_count):
        message = grid_pattern.GetItem(row, 6).Name or ""
        date_str = grid_pattern.GetItem(row, 1).Name or ""

        if subject != message:
            continue

        parsed_date = _parse_date(date_str)
        if parsed_date is None:
            continue

        if latest_date is None or parsed_date > latest_date:
            latest_row = row
            latest_date = parsed_date

    return latest_row


def _get_sent_table_grid(root_web_area):
    """
    Returns the grid pattern for the sent messages table.

    Args:
        root_web_area: The root web area control.

    Returns:
        GridPattern: The grid pattern of the sent messages table.
    """
    table = wait_for_control(
        root_web_area.TableControl, {"AutomationId": "dtSent"}, search_depth=50
    )
    return table.GetPattern(auto.PatternId.GridPattern)


def _open_row_menu(grid_pattern, row: int, root_web_area):
    """
    Clicks the row's action menu button and returns the visible popup.

    Args:
        grid_pattern: The grid pattern of the sent messages table.
        row (int): The row index to open the menu for.
        root_web_area: The root web area control.

    Returns:
        ListControl: The visible dropdown menu popup.

    Raises:
        TimeoutError: If the dropdown menu is not found.
    """
    grid_pattern.GetItem(row, 10).Click(simulateMove=False, waitTime=0)
    time.sleep(3)

    for class_name in ("dropdown-menu show", "dropdown-menu"):
        try:
            return wait_for_control(
                root_web_area.ListControl,
                {"ClassName": class_name},
                search_depth=50,
                timeout=15,
            )
        except TimeoutError:
            continue

    raise TimeoutError("Could not find dropdown menu with any method")


def _hover_and_get_save_link(menu_popup):
    """
    Hovers over the 'Gem' item and returns the 'Gem som PDF' hyperlink.

    Args:
        menu_popup: The dropdown menu popup control.

    Returns:
        HyperlinkControl: The 'Gem som PDF' hyperlink control.
    """
    gem_item = wait_for_control(
        menu_popup.ListItemControl, {"Name": " Gem"}, search_depth=50
    )
    gem_item.SetFocus()
    pos = gem_item.GetClickablePoint()
    auto.MoveTo(pos[0], pos[1], moveSpeed=0.5, waitTime=0)

    return wait_for_control(
        menu_popup.HyperlinkControl, {"Name": "Gem som PDF"}, search_depth=50
    )


def _wait_for_receipt_download(
    download_path: Path, existing: set, timeout: int = 120
) -> str:
    """
    Waits for a new receipt PDF to appear in the download folder.

    Args:
        download_path (Path): The path to the downloads folder.
        existing (set): The set of existing receipt files before the download.
        timeout (int): Maximum time to wait for the download, in seconds.

    Returns:
        str: The path to the downloaded receipt file.

    Raises:
        FileNotFoundError: If no receipt file is found within the timeout period.
    """
    _DOWNLOAD_TIMEOUT = 30
    start_time = time.time()

    while time.time() - start_time < _DOWNLOAD_TIMEOUT:
        if next(download_path.glob("Meddelelse*.crdownload"), None):
            break
        time.sleep(0.5)

    while time.time() - start_time < timeout:
        new_receipts = set(download_path.glob("Meddelelse*.pdf")) - existing
        if new_receipts:
            receipt = max(new_receipts, key=lambda p: p.stat().st_mtime)
            logger.info("Receipt downloaded: %s", receipt)
            return str(receipt)
        time.sleep(1)

    raise FileNotFoundError(
        "No file starting with 'Meddelelse' and ending with '.pdf' "
        "was found within the timeout period."
    )


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
    """
    try:
        root_web_area = wait_for_control(
            auto.DocumentControl, {"AutomationId": "RootWebArea"}, search_depth=30
        )

        grid_pattern = _get_sent_table_grid(root_web_area)
        row_count = grid_pattern.RowCount

        latest_row = _find_latest_sent_row(grid_pattern, row_count, subject)
        if latest_row is None:
            logger.error("Message not sent.")
            raise RuntimeError("Message not sent.")

        logger.info("Using latest matching row %s", latest_row)

        menu_popup = _open_row_menu(grid_pattern, latest_row, root_web_area)

        menu_popup = wait_for_control(
            root_web_area.ListControl,
            {"ClassName": "dropdown-menu show"},
            search_depth=50,
        )

        save_link = _hover_and_get_save_link(menu_popup)

        download_path = Path.home() / "Downloads"
        existing_receipts = set(download_path.glob("Meddelelse*.pdf"))

        save_link.Click(simulateMove=False, waitTime=0)

        return _wait_for_receipt_download(download_path, existing_receipts)

    except Exception as e:
        logger.error("Error while downloading the receipt from EDI Portal: %s", e)
        raise


def rename_file(file_path: str, new_name: str, extension: str) -> str:
    """
    Renames a file and returns its new path.

    Args:
        file_path (str): Full path to the file to rename.
        new_name   (str): New filename without extension.
        extension  (str): New extension (e.g. '.pdf').

    Returns:
        str: Absolute path to the renamed file.

    Raises:
        FileNotFoundError: If the source file does not exist.
        OSError:           If the rename operation fails.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    new_file_path = path.parent / f"{new_name}{extension}"
    path.rename(new_file_path)
    return str(new_file_path)


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
                date_str = grid_pattern.GetItem(row, 1).Name or ""

                # Check if message contains the target text
                if subject not in message:
                    continue

                # Parse and check if date is older than 1 month
                parsed_date = _parse_date(date_str)
                if parsed_date is None:
                    continue

                # Both conditions must be true: message contains subject AND date is older than 1 month
                if parsed_date > one_month_ago:
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
