import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_reject_overlapping_model_aliases() -> None:
    with pytest.raises(ValidationError, match="Model role aliases overlap"):
        Settings(
            _env_file=None,
            MODEL_1_ALIASES=("shared",),
            MODEL_2_ALIASES=("shared",),
        )


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
