import pytest

from publiceye.core.provider import detect_target_type
from publiceye.core.models import TargetType


@pytest.mark.parametrize(
    "value,expected",
    [
        ("example.com", TargetType.DOMAIN),
        ("sub.example.co.uk", TargetType.DOMAIN),
        ("8.8.8.8", TargetType.IP),
        ("a.b@example.com", TargetType.EMAIL),
        ("not a target", TargetType.UNKNOWN),
        ("999.1.1.1", TargetType.UNKNOWN),
    ],
)
def test_detect_target_type(value, expected):
    assert detect_target_type(value) is expected
