"""Helper functions for subprocesses"""

import logging
import os
import zipfile
import zoneinfo
from datetime import datetime

# Constants for CPR parsing
CPR_LENGTH = 10
SSSS_0_1999_MAX = 1999
SSSS_2000_MIN = 2000
SSSS_4999_MAX = 4999
SSSS_5000_MIN = 5000
SSSS_8999_MAX = 8999
SSSS_9000_MIN = 9000
SSSS_9999_MAX = 9999
YY_CENTURY_SPLIT = 37
AGE_16 = 16
AGE_22 = 22

logger = logging.getLogger(__name__)


def cpr_to_birthdate(ssn: str) -> datetime:
    """
    Convert a Danish CPR number (DDMMYYSSSS) to a birth-date
    with the correct century.

    Century rules  (DST / CPR):
      personal 0-1999 → 1900-1999 if YY ≥ 37 else 2000-2036
      personal 2000-4999 → 1900-1999
      personal 5000-8999 → 1900-1999 if YY ≥ 37 else 2000-2036
      personal 9000-9999 → 1800-1899 if YY ≥ 37 else 2000-2036
    """

    if len(ssn) != CPR_LENGTH or not ssn.isdigit():
        raise ValueError("CPR number must be exactly 10 digits (DDMMYYSSSS)")

    day = int(ssn[0:2])
    month = int(ssn[2:4])
    yy = int(ssn[4:6])
    ssss = int(ssn[6:10])

    # Determine the full year
    if 0 <= ssss <= SSSS_0_1999_MAX:
        year = 1900 + yy if yy >= YY_CENTURY_SPLIT else 2000 + yy
    elif SSSS_2000_MIN <= ssss <= SSSS_4999_MAX:
        year = 1900 + yy
    elif SSSS_5000_MIN <= ssss <= SSSS_8999_MAX:
        year = 1900 + yy if yy >= YY_CENTURY_SPLIT else 2000 + yy
    elif SSSS_9000_MIN <= ssss <= SSSS_9999_MAX:
        year = 1800 + yy if yy >= YY_CENTURY_SPLIT else 2000 + yy
    else:
        logger.error("Invalid CPR personal-number range")
        raise ValueError("Invalid CPR personal-number range")

    # Let datetime validate day/month automatically
    # Attach Copenhagen timezone
    return datetime(year, month, day, tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen"))


# def future_dates(ssn: str) -> tuple:
#     """Calculate the dates 16 and 22 years into the future from a CPR number."""
#     try:
#         birth_date = cpr_to_birthdate(ssn)

#         # Handle leap year by checking if the target date is valid
#         def add_years_safely(date, years):
#             target_year = date.year + years
#             try:
#                 return date.replace(year=target_year)
#             except ValueError:
#                 # If Feb 29 doesn't exist in target year, use Feb 28
#                 return date.replace(year=target_year, day=28)

#         date_16_years = add_years_safely(birth_date, 16).replace(
#             tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
#         )
#         date_22_years = add_years_safely(birth_date, 22).replace(
#             tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
#         )

#         return date_16_years, date_22_years

#     except Exception as e:
#         logger.error("Error calculating future dates: %s", e)
#         raise


# def is_under_16(ssn: str) -> bool:
#     """Check if a person is under 16 years old."""
#     birth_date = cpr_to_birthdate(ssn)
#     today = datetime.now(tz=zoneinfo.ZoneInfo("Europe/Copenhagen"))
#     age = (
#         today.year
#         - birth_date.year
#         - ((today.month, today.day) < (birth_date.month, birth_date.day))
#     )
#     return age < 16


def zip_folder_contents(folder_path: str, zip_filename: str) -> None:
    """
    Zips all files in the specified folder (non-recursive) into a .zip archive.

    Args:
        folder_path (str): Path to the folder containing files to zip.
        zip_filename (str): Full path (including .zip filename) for the output zip file.
    """
    try:
        with zipfile.ZipFile(
            zip_filename, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zipf:
            for filename in os.listdir(folder_path):
                full_path = os.path.join(folder_path, filename)
                if os.path.isfile(full_path):
                    zipf.write(full_path, arcname=filename)
    except Exception as e:
        logger.error("Error zipping folder: %s", e)
