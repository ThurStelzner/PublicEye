import pytest

from publiceye.core.provider import detect_target_type
from publiceye.core.models import TargetType


@pytest.mark.parametrize(
    "value,expected",
    [
        ("example.com", TargetType.DOMAIN),
        ("sub.example.co.uk", TargetType.DOMAIN),
        ("8.8.8.8", TargetType.IP),
        ("01310-100", TargetType.CEP),
        ("01310100", TargetType.CEP),
        ("11.222.333/0001-81", TargetType.CNPJ),
        ("11222333000181", TargetType.CNPJ),
        ("11.222.333/0001-80", TargetType.UNKNOWN),
        ("-23.55,-46.63", TargetType.WEATHER),
        ("90,180", TargetType.WEATHER),
        ("91,0", TargetType.UNKNOWN),
        ("a.b@example.com", TargetType.EMAIL),
        ("not a target", TargetType.UNKNOWN),
        ("999.1.1.1", TargetType.UNKNOWN),
    ],
)
def test_detect_target_type(value, expected):
    assert detect_target_type(value) is expected
