"""
Unit tests for the SSRF-safe fetcher.

DNS resolution is patched via unittest.mock so no real network calls are made.
Each test injects a controlled getaddrinfo result and asserts that _validate_url
either passes or raises ValueError with the right reason.
"""

import ipaddress
import pytest
from unittest.mock import patch

from hn_search.fetcher import _validate_url, _is_safe_host, SKIP_DOMAINS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_addrinfo(ip: str) -> list:
    """Build a minimal getaddrinfo return value for a single IP."""
    family = 10 if ":" in ip else 2  # AF_INET6 or AF_INET
    return [(family, 1, 6, "", (ip, 0))]


def _patch_dns(ip: str):
    """Context manager: make every getaddrinfo call return the given IP."""
    return patch("hn_search.fetcher.socket.getaddrinfo", return_value=_make_addrinfo(ip))


# ---------------------------------------------------------------------------
# _is_safe_host
# ---------------------------------------------------------------------------

class TestIsSafeHost:
    def test_public_ipv4_allowed(self):
        with _patch_dns("93.184.216.34"):  # example.com
            assert _is_safe_host("example.com") is True

    def test_loopback_ipv4_rejected(self):
        with _patch_dns("127.0.0.1"):
            assert _is_safe_host("localhost") is False

    def test_loopback_ipv6_rejected(self):
        with _patch_dns("::1"):
            assert _is_safe_host("localhost") is False

    def test_private_rfc1918_rejected(self):
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
            with _patch_dns(ip):
                assert _is_safe_host("internal") is False, f"{ip} should be rejected"

    def test_link_local_ipv4_rejected(self):
        # 169.254.x.x — cloud metadata range
        with _patch_dns("169.254.169.254"):
            assert _is_safe_host("metadata.internal") is False

    def test_link_local_ipv6_rejected(self):
        with _patch_dns("fe80::1"):
            assert _is_safe_host("link-local") is False

    def test_multicast_rejected(self):
        with _patch_dns("224.0.0.1"):
            assert _is_safe_host("multicast") is False

    def test_unspecified_rejected(self):
        with _patch_dns("0.0.0.0"):
            assert _is_safe_host("unspecified") is False

    def test_dns_failure_rejected(self):
        import socket
        with patch("hn_search.fetcher.socket.getaddrinfo", side_effect=socket.gaierror):
            assert _is_safe_host("nonexistent.invalid") is False


# ---------------------------------------------------------------------------
# _validate_url — scheme checks
# ---------------------------------------------------------------------------

class TestValidateUrlScheme:
    def test_http_allowed(self):
        with _patch_dns("93.184.216.34"):
            url, host = _validate_url("http://example.com/article")
            assert host == "example.com"

    def test_https_allowed(self):
        with _patch_dns("93.184.216.34"):
            url, host = _validate_url("https://example.com/article")
            assert host == "example.com"

    def test_ftp_rejected(self):
        with pytest.raises(ValueError, match="Scheme not allowed"):
            _validate_url("ftp://example.com/file")

    def test_file_rejected(self):
        with pytest.raises(ValueError, match="Scheme not allowed"):
            _validate_url("file:///etc/passwd")

    def test_javascript_rejected(self):
        with pytest.raises(ValueError, match="Scheme not allowed"):
            _validate_url("javascript:alert(1)")


# ---------------------------------------------------------------------------
# _validate_url — SSRF via DNS rebinding / private IPs
# ---------------------------------------------------------------------------

class TestValidateUrlSSRF:
    def test_localhost_rejected(self):
        with _patch_dns("127.0.0.1"):
            with pytest.raises(ValueError, match="private/reserved"):
                _validate_url("http://localhost/admin")

    def test_metadata_endpoint_rejected(self):
        # AWS/GCP/Azure cloud metadata address
        with _patch_dns("169.254.169.254"):
            with pytest.raises(ValueError, match="private/reserved"):
                _validate_url("http://169.254.169.254/latest/meta-data/")

    def test_internal_hostname_resolving_to_private_rejected(self):
        with _patch_dns("10.0.0.1"):
            with pytest.raises(ValueError, match="private/reserved"):
                _validate_url("http://internal.corp/secret")

    def test_redirect_target_with_private_ip_rejected(self):
        # Simulates a redirect to an internal address
        with _patch_dns("192.168.0.1"):
            with pytest.raises(ValueError, match="private/reserved"):
                _validate_url("https://internal-redirect.example/path")

    def test_ipv6_loopback_rejected(self):
        with _patch_dns("::1"):
            with pytest.raises(ValueError, match="private/reserved"):
                _validate_url("http://[::1]/admin")


# ---------------------------------------------------------------------------
# _validate_url — skip list
# ---------------------------------------------------------------------------

class TestValidateUrlSkipList:
    @pytest.mark.parametrize("domain", [
        "twitter.com", "x.com", "youtube.com", "youtu.be",
        "instagram.com", "facebook.com", "reddit.com",
    ])
    def test_skip_domains_rejected(self, domain):
        with _patch_dns("93.184.216.34"):  # DNS would resolve fine
            with pytest.raises(ValueError, match="skip list"):
                _validate_url(f"https://{domain}/some/path")

    def test_www_prefix_skip_domain_rejected(self):
        with _patch_dns("93.184.216.34"):
            with pytest.raises(ValueError, match="skip list"):
                _validate_url("https://www.twitter.com/user")


# ---------------------------------------------------------------------------
# _validate_url — extension skip
# ---------------------------------------------------------------------------

class TestValidateUrlExtensions:
    @pytest.mark.parametrize("ext", [".pdf", ".mp4", ".mp3", ".zip", ".png", ".jpg"])
    def test_skipped_extensions(self, ext):
        with _patch_dns("93.184.216.34"):
            with pytest.raises(ValueError, match="extension"):
                _validate_url(f"https://example.com/file{ext}")

    def test_html_extension_allowed(self):
        with _patch_dns("93.184.216.34"):
            url, _ = _validate_url("https://example.com/article.html")
            assert "article.html" in url
