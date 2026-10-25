from app.config import ALLOW_REAL_CALLS

class TelephonyNotConfigured(RuntimeError):
    pass

def place_call(*, phone: str, script: str, customer_reference: str) -> dict:
    """Safe boundary for a provider adapter. This starter never places real calls."""
    if not ALLOW_REAL_CALLS:
        raise TelephonyNotConfigured(
            "Real calling is disabled. Use the dashboard's simulated call workflow."
        )
    # Deliberately fail closed until an approved provider adapter, credentials,
    # webhook validation, caller ID, and compliance controls have been implemented.
    raise TelephonyNotConfigured(
        "No provider adapter is installed. Configure an approved provider integration first."
    )
