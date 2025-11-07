"""Module for general configurations of the process"""

MAX_RETRY = 10

# ----------------------
# Queue population settings
# ----------------------
MAX_CONCURRENCY = 100  # tune based on backend capacity
MAX_RETRIES = 3  # transient failure retries per item
RETRY_BASE_DELAY = 0.5  # seconds (exponential backoff)

# ----------------------
# Solteq Tand application settings
# ----------------------
APP_PATH = "C:\\Program Files (x86)\\TM Care\\TM Tand\\TMTand.exe"
TMP_FOLDER = "C:\\tmp\\tmt"
ROMEXIS_ROOT_PATH = r"\\SRVAPPROMEX04\romexis_images$"

# ----------------------
# Document
# ----------------------
DOCUMENT_TYPE = "Udskrivning - 22 år!$#"
JOURNAL_CONTINUATION_TEXT = "Besked til privat tandklinik: "
JOURNAL_CONTINUATION_REPLACEMENT_TEXT = "Følgende oplysninger skal medsendes til privat tandlæge i forbindelse med udskrivning: "
