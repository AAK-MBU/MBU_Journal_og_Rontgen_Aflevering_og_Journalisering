"""
This module handles the processing of images.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from mbu_dev_shared_components.romexis.helper_functions import (
    add_black_bar_and_text_to_image,
)

from helpers import config

logger = logging.getLogger(__name__)


def build_source_path(raw_path: str) -> str:
    """Convert relative path to full UNC path."""
    return os.path.join(
        config.ROMEXIS_ROOT_PATH,
        raw_path[3:].replace("romexis_images/", "").replace("/", "\\"),
    )


def format_image_date(date_value) -> str:
    """Format YYYYMMDD integer to DD/MM/YYYY string."""
    try:
        return (
            datetime.strptime(str(date_value), "%Y%m%d")
            .replace(tzinfo=ZoneInfo("Europe/Copenhagen"))
            .strftime("%d/%m/%Y")
        )
    except (ValueError, TypeError):
        logger.warning("Invalid image_date: %s", date_value)
        return None


def log_file_info(file_path: str, image_id=None) -> None:
    """Log what kind of file this is, for diagnosing a processing failure.

    Never raises, so it is safe to call from an except block.
    """
    lines = [f"image_id={image_id}", f"path={file_path}"]

    try:
        if not os.path.exists(file_path):
            lines.append("exists=False")
            logger.error("FILE INFO: %s", " | ".join(lines))
            return

        lines.append(f"size={os.path.getsize(file_path)}")

        with open(file_path, "rb") as f:
            head = f.read(132)

        lines.append(f"first_bytes={head[:12].hex(' ')}")

        is_dicom = head[128:132] == b"DICM"
        lines.append(f"dicom={is_dicom}")

        if is_dicom:
            try:
                import pydicom  # noqa: PLC0415

                ds = pydicom.dcmread(file_path, stop_before_pixels=True)
                lines.append(f"transfer_syntax={ds.file_meta.TransferSyntaxUID}")
                lines.append(f"syntax_name={ds.file_meta.TransferSyntaxUID.name}")
                lines.append(f"sop_class={ds.get('SOPClassUID', '')}")
                lines.append(f"modality={ds.get('Modality', '')}")
                lines.append(f"size_px={ds.get('Columns', '?')}x{ds.get('Rows', '?')}")
                lines.append(f"bits={ds.get('BitsAllocated', '')}")
                lines.append(f"photometric={ds.get('PhotometricInterpretation', '')}")
                lines.append(f"frames={ds.get('NumberOfFrames', 1)}")
            except ImportError:
                lines.append("pydicom=NOT INSTALLED")
            except Exception as e:  # noqa: BLE001
                lines.append(f"dicom_read_error={type(e).__name__}: {e}")

    except Exception as e:  # noqa: BLE001
        lines.append(f"log_error={type(e).__name__}: {e}")

    logger.error("FILE INFO: %s", " | ".join(lines))


def process_images_threaded(
    images_data, destination_path, ssn, person_name, db_handler
) -> None:
    """Process images concurrently using threads."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}

        for img in images_data:
            gamma_data = db_handler.get_gamma_data(image_id=img["image_id"])
            source_path = build_source_path(img["file_path"])

            if not os.path.exists(source_path):
                logger.warning("Skipping missing file: %s", source_path)
                continue

            formatted_date = format_image_date(img.get("image_date"))
            image_type = img.get("image_type")

            future = executor.submit(
                add_black_bar_and_text_to_image,
                source_path,
                destination_path,
                ssn,
                person_name,
                formatted_date,
                image_type,
                rotation_angle=img.get("rotation_angle", 0),
                is_mirror=img.get("is_mirror", False),
                gamma_value=(
                    gamma_data[0]["gamma_value"]
                    if gamma_data and gamma_data[0].get("gamma_value")
                    else 1.0
                ),
            )
            futures[future] = (img["image_id"], source_path)

        for future in as_completed(futures):
            image_id, source_path = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(
                    "Image processing failed for image_id=%s: %s: %s",
                    image_id,
                    type(e).__name__,
                    e,
                )
                log_file_info(source_path, image_id)
                raise


def clear_img_files_in_folder(folder_path: str) -> None:
    """Clear all .img files in the specified folder."""
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) and file_path.endswith(".img"):
                logger.info("Removing file: %s", file_path)
                os.remove(file_path)
        except OSError as e:
            logger.error("Error removing file %s: %s", file_path, e)
