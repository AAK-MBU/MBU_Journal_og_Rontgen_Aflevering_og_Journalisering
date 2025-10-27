"""
This module handles the creation and splitting of ZIP files.
It includes functions to create a ZIP file from images, split a ZIP file into smaller parts
if it exceeds a specified size, and process the ZIP file to check its size and split it if necessary.
"""

import logging
import os
import zipfile
from pathlib import Path

from mbu_dev_shared_components.romexis.helper_functions import (
    zip_folder_contents,
)

from helpers import config

logger = logging.getLogger(__name__)


def create_zip_from_images(
    ssn: str, person_name: str, source_folder: str
) -> tuple[str, str]:
    """Zip processed image files.

    Args:
        ssn: Patient's social security number.
        person_name: Patient's name, used for the ZIP file's name.
        source_folder: Path to the folder containing the processed image files.

    Returns:
        zip_full_path: Full path to the created ZIP.
        zip_filename: The name of the ZIP file (without the path).
    """
    if not os.path.isdir(source_folder):
        logger.error("Source folder does not exist: %s", source_folder)
        raise FileNotFoundError(f"Source folder does not exist: {source_folder}")

    if not any(Path(source_folder).iterdir()):
        logger.error("Source folder is empty, nothing to zip: %s", source_folder)
        raise ValueError(f"Source folder is empty, nothing to zip: {source_folder}")

    zip_file_path = os.path.join(config.TMP_FOLDER, ssn, "edi_portal")

    if not os.path.exists(zip_file_path):
        os.makedirs(zip_file_path, exist_ok=True)

    zip_filename = f"{person_name}.zip"
    zip_full_path = os.path.join(zip_file_path, zip_filename)

    zip_folder_contents(source_folder, zip_full_path)

    logger.info("Zip file was created: %s", zip_full_path)

    return zip_full_path, zip_filename


def split_zip(
    input_zip_path: str, output_dir: str | None = None, max_size: int | None = None
) -> Path:
    """
    Split a ZIP file into smaller parts if it exceeds the specified size.

    Args:
        input_zip_path (str): Path to the input ZIP file.
        output_dir (str | None): Directory to save the split ZIP files. If None, a new directory will be created.
        max_size (int | None): Maximum size of each split ZIP file in bytes.

    Returns:
        Path: Path to the directory containing the split ZIP files.
    """
    input_path = Path(input_zip_path)

    if not input_path.is_file():
        logger.error("Input ZIP file does not exist: %s", input_zip_path)
        raise FileNotFoundError(f"Input ZIP file does not exist: {input_zip_path}")

    if output_dir is None:
        output_dir = input_path.parent / f"{input_zip_path.stem}_split"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(input_path, "r") as original_zip:
        file_infos = original_zip.infolist()

        buckets = []
        current_bucket = []
        current_size = 0

        for info in file_infos:
            file_compressed_size = info.compress_size
            if file_compressed_size > max_size:
                if current_bucket:
                    buckets.append(current_bucket)
                    current_bucket = []
                    current_size = 0
                buckets.append([info])
                continue

            if current_size + file_compressed_size > max_size:
                buckets.append(current_bucket)
                current_bucket = []
                current_size = 0

            current_bucket.append(info)
            current_size += file_compressed_size

        if current_bucket:
            buckets.append(current_bucket)

        for idx, bucket in enumerate(buckets, start=1):
            part_zip_path = output_dir / f"{input_path.stem}_part{idx}.zip"
            with zipfile.ZipFile(
                part_zip_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as part_zip:
                for info in bucket:
                    data = original_zip.read(info.filename)
                    part_zip.writestr(info, data)

    logger.info("Split into %d ZIP file(s) in folder: %s", len(buckets), output_dir)
    return output_dir


def process_zip(input_zip_path: str, max_size: int | None = None) -> Path:
    """
    Check the size of the ZIP file and split if necessary.

    Args:
        input_zip_path (str): Path to the input ZIP file.
        max_size (int | None): Maximum size of each split ZIP file in bytes. Default is 50 MB.

    returns:
        Path | None: Path to the directory containing the split ZIP files, or None if no splitting was needed.
    """
    input_path = Path(input_zip_path)

    if not input_path.is_file():
        logger.error("Input ZIP file does not exist: %s", input_zip_path)
        raise FileNotFoundError(f"Input ZIP-fil findes ikke: {input_zip_path}")

    zip_size = input_path.stat().st_size

    if max_size is None:
        max_size = 50 * 1024 * 1024

    if zip_size > max_size:
        output_dir = split_zip(
            input_zip_path=input_path, output_dir=None, max_size=max_size
        )
        return output_dir

    return input_path
