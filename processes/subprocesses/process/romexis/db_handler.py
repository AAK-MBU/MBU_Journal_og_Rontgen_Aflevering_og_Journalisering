"""
Database handler for retrieving person and image data.
"""

import logging
import time
from functools import wraps

import pyodbc
from mbu_rpa_core.exceptions import ProcessError

logger = logging.getLogger(__name__)


def retry_on_connection_error(max_attempts=3, delay=2, backoff=2):
    """
    Decorator to retry database operations on connection errors.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except pyodbc.OperationalError as e:
                    last_exception = e
                    error_code = e.args[0] if e.args else None

                    # Check if it's a connection-related error
                    if error_code in ("08001", "08S01", "HYT00"):
                        if attempt < max_attempts:
                            logger.warning(
                                "DB connection error on attempt %d/%d: %s. "
                                "Retrying in %.1f seconds...",
                                attempt,
                                max_attempts,
                                str(e),
                                current_delay,
                            )
                            time.sleep(current_delay)
                            current_delay *= backoff
                        else:
                            logger.error(
                                "DB connection failed after %d attempts: %s",
                                max_attempts,
                                str(e),
                            )
                    else:
                        # Non-connection error, don't retry
                        raise
                except Exception:
                    # Non-pyodbc errors should not be retried
                    raise

            # If we exhausted all retries, raise the last exception
            if last_exception:
                error_msg = (
                    f"Failed to connect to database after {max_attempts} attempts"
                )
                raise ProcessError(error_msg) from last_exception

        return wrapper

    return decorator


@retry_on_connection_error(max_attempts=3, delay=2, backoff=2)
def get_person_info(db_handler, ssn: str) -> tuple | None:
    """Retrieve and validate person data from the database."""
    try:
        person_data = db_handler.get_person_data(external_id=ssn)
    except ProcessError as e:
        logger.error("Error retrieving person data: %s", e)
        raise

    if not person_data:
        logger.info("No person data found for SSN.")
        return None

    person = person_data[0]

    if not person.get("person_id"):
        logger.info("Person ID not found for SSN.")
        return None

    person_id = person["person_id"]

    if not person.get("first_name") and not person.get("last_name"):
        logger.info("Person name not found for SSN.")
        return None

    person_name = " ".join(
        filter(
            None,
            [
                person.get("first_name"),
                person.get("second_name"),
                person.get("third_name"),
                person.get("last_name"),
            ],
        )
    )

    return person_id, person_name


@retry_on_connection_error(max_attempts=3, delay=2, backoff=2)
def get_image_data(db_handler, person_id: str) -> list:
    """Retrieve image IDs and image data from the database."""
    image_ids = []
    images_data = []

    image_ids = db_handler.get_image_ids(patient_id=person_id)

    if image_ids:
        images_data = db_handler.get_image_data(image_ids=image_ids)

    return images_data
