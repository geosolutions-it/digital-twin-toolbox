import pytest
from pydantic import ValidationError

from app.models.config import PointCloudConfig


def test_defaults():
    c = PointCloudConfig()
    assert c.sample_radius is None
    assert c.to_ellipsoidal_height is False
    assert c.ground_classification is False
    assert c.colorization_image is None


def test_coercion_and_extra_ignored():
    # geometric_error_scale_factor is no longer a field; it must be ignored, not error
    c = PointCloudConfig(sample_radius="0.5", to_ellipsoidal_height="true", geometric_error_scale_factor=4)
    assert c.sample_radius == 0.5
    assert c.to_ellipsoidal_height is True
    assert not hasattr(c, "geometric_error_scale_factor")


def test_blank_sample_radius_is_auto():
    assert PointCloudConfig(sample_radius="").sample_radius is None
    assert PointCloudConfig(sample_radius="  ").sample_radius is None


def test_fallback_epsg():
    assert PointCloudConfig().horizontal_epsg is None
    assert PointCloudConfig(horizontal_epsg="").horizontal_epsg is None
    c = PointCloudConfig(horizontal_epsg="25833", vertical_epsg="5773")
    assert c.horizontal_epsg == 25833 and c.vertical_epsg == 5773


def test_invalid_raises():
    with pytest.raises(ValidationError):
        PointCloudConfig(sample_radius="not-a-number")
