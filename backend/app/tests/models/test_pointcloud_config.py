import pytest
from pydantic import ValidationError

from app.models.config import PointCloudConfig


def test_defaults():
    c = PointCloudConfig()
    assert c.geometric_error_scale_factor == 1.0
    assert c.to_ellipsoidal_height is False
    assert c.sample_radius is None
    assert c.colorization_image is None


def test_coercion_and_extra_ignored():
    c = PointCloudConfig(geometric_error_scale_factor="2", sample_radius="0.5", unknown="x")
    assert c.geometric_error_scale_factor == 2.0
    assert c.sample_radius == 0.5
    assert not hasattr(c, "unknown")


def test_invalid_raises():
    with pytest.raises(ValidationError):
        PointCloudConfig(sample_radius="not-a-number")
