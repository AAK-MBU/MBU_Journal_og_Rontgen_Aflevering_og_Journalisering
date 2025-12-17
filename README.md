# MBU Journal og Rontgen Aflevering og Journalisering

Automated RPA process for transferring medical records and x-ray files to private dental clinics via EDI Portal.

## Overview

This process automates the workflow for 22-year-old patient handovers:
- Retrieves patient data from Solteq Tand application
- Gathers x-ray images from Romexis database
- Prepares and sends medical documents via EDI Portal
- Creates receipt documentation and journal entries

## Requirements

- Python 3.11+
- Windows environment (for Solteq Tand integration)
- Access to Solteq Tand application
- EDI Portal credentials
- Database connections configured

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AAK-MBU/MBU_Journal_og_Rontgen_Aflevering_og_Journalisering.git
cd MBU_Journal_og_Rontgen_Aflevering_og_Journalisering
```

2. Create virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
# or
uv pip install .
```
