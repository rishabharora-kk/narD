from unittest.mock import patch
import pytest
from nard.config import Source,approved
from nard.security import FetchDenied,checked_url,public_addresses

@pytest.mark.parametrize("url",[
    "http://example.org/","https://example.org.evil.test/","https://user@example.org/",
    "https://example.org:8443/","https://127.0.0.1/","https://example.org/#fragment",
    "https://[::1]/","https://example.org@evil.test/",
])
def test_denied(url):
    with pytest.raises(FetchDenied): checked_url(url,"example.org")

def test_url_path_and_query():
    assert checked_url("https://example.org/abc?q=2","example.org")==("example.org","/abc?q=2")

def test_dns_private_or_mixed_fails_closed():
    with patch("socket.getaddrinfo",return_value=[
        (2,1,6,"",("1.1.1.1",443)),(2,1,6,"",("127.0.0.1",443))]):
        with pytest.raises(FetchDenied): public_addresses("example.org")

def test_default_sources_cannot_fetch():
    assert not approved(Source(id="sample",family="patent",url="https://example.org",enabled=True))
