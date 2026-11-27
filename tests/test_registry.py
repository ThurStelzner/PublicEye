from publiceye.core.models import TargetType
from publiceye.core.registry import all_providers, load_builtin, providers_for


def test_builtin_providers_registered():
    load_builtin()
    names = set(all_providers())
    assert {"rdap", "crtsh"} <= names


def test_providers_for_domain_includes_rdap_and_crtsh():
    load_builtin()
    names = {cls.name for cls in providers_for(TargetType.DOMAIN)}
    assert {"rdap", "crtsh"} <= names


def test_providers_for_ip_excludes_crtsh():
    load_builtin()
    names = {cls.name for cls in providers_for(TargetType.IP)}
    assert "rdap" in names
    assert "crtsh" not in names
