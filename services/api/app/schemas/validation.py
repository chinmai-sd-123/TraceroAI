"""Input limits and cleaning shared by the request schemas.

The length limits mirror the indexed columns in app/db/models.py: a value that
passes validation can always be stored, so a long project id is a 422 for the
client instead of a database error and a 500.
"""

from typing import Any

PROJECT_ID_MAX_LENGTH = 100
ENVIRONMENT_MAX_LENGTH = 50
STATUS_MAX_LENGTH = 50
MODEL_MAX_LENGTH = 100
DATASET_ID_MAX_LENGTH = 100
DATASET_NAME_MAX_LENGTH = 200
VERSION_MAX_LENGTH = 100

# Far above any real retrieval depth. The request body limit
# (BodySizeLimitMiddleware, settings.max_request_bytes) is the overall cap on size.
MAX_CHUNKS_PER_TRACE = 200


def strip_nul(value: Any) -> Any:
    """Remove NUL characters from every string in a JSON-like value, keys included.

    Postgres can't store NUL in text columns or JSONB, so leaving one in turns a
    harmless input into a failed insert.
    """
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {strip_nul(key): strip_nul(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strip_nul(item) for item in value]
    return value
