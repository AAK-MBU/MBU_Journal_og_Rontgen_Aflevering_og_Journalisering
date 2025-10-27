"""Module to hold application-wide context data."""


class AppContext:
    """Class to hold application-wide context data."""

    def __init__(self):
        self.primary_clinic_and_patient_data = None
        self.extern_clinic_data = None
        self.administrative_note = None
        # Add other shared data as needed

    def reset(self):
        """Reset all context data to None."""

        self.primary_clinic_and_patient_data = None
        self.extern_clinic_data = None
        self.administrative_note = None
        # Reset other shared data as needed


app_context = AppContext()
