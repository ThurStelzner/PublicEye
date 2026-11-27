from publiceye.providers.crtsh import _is_subdomain_of


def test_valid_subdomains():
    assert _is_subdomain_of("www.example.com", "example.com")
    assert _is_subdomain_of("a.b.example.com", "example.com")


def test_rejects_suffix_without_dot_boundary():
    # testexample.com termina com "example.com" mas não é subdomínio.
    assert not _is_subdomain_of("testexample.com", "example.com")


def test_rejects_non_hostnames():
    assert not _is_subdomain_of("user@example.com", "example.com")
    assert not _is_subdomain_of("some ca - example.com", "example.com")
    assert not _is_subdomain_of("example.com", "example.com")
