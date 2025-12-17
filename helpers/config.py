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

ADM_NOTE = "Administrativt notat 'Udskrivning 22 år gennemført af robot. Sendt information, journal og billedmateriale til privat tandklinik via EDI-portal. Se dokumentskab'"
ADM_NOTE_LOOKUP = "Udskrivning 22 år gennemført af robot. Sendt information, journal og billedmateriale til privat tandklinik via EDI-portal. Se dokumentskab"
EXTERN_CLINIC_PHONE_NUMBER_NOT_SET_MESSAGE = '{"message": "Der mangler et telefonnummer på den private tandklinik i Solteq", "code": "Tilføj telefonnummer i Solteq for den valgte tandklinik og genstart"}'
PHONE_NUMBER_MISMATCH_MESSAGE = '{"message": "Telefonnummeret på tandklinikken i Solteq og EDI-portalen skal være ens", "code": "Kontakt Tandplejens administration, tandplejen@mbu.aarhus.dk, og bed om at få tandklinikkens telefonnummer rettet i Solteq. Afvent svar. Du kan genstarte processen, når telefonnummeret er ændret i Solteq"}'
DASHBOARD_PROCESS_NAME = "Udskrivning 22 år"
DASHBOARD_STEP_8_NAME = "Journalmateriale sendt og journaliseret"
