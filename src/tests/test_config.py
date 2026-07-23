import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_reject_alternate_model_routes() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, MODEL_1_FLASH="alternate/model")


def test_settings_reject_invalid_distance_ordering() -> None:
    with pytest.raises(
        ValidationError,
        match="RETRIEVAL_ABSOLUTE_DISTANCE_FLOOR cannot exceed",
    ):
        Settings(
            _env_file=None,
            RETRIEVAL_ABSOLUTE_DISTANCE_FLOOR=0.8,
            RETRIEVAL_ABSOLUTE_DISTANCE_CEILING=0.4,
        )
