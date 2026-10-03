"""
SSRF-safe article fetcher.

Safety guarantees
-----------------
- Only http/https schemes.
- Resolves hostname; rejects private/loopback/link-local/multicast/reserved IPs.
- Follows redirects manually (max 3), re-checking each hop.
- Hard body cap (~2 MB), HTML content-type only.
- Respects robots.txt (cached per host).
- Global semaphore (10) + per-host semaphore (2).
- Configurable domain skip list.
"""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

logger = logging.getLogger(__name__)

_MAX_BODY = 2 * 1024 * 1024          # 2 MB
_MAX_REDIRECTS = 3
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 20
_MIN_CONTENT_LEN = 0                  # robots fetch can be tiny
_GLOBAL_SEM = asyncio.Semaphore(10)
_HOST_SEMS: dict[str, asyncio.Semaphore] = {}
_ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}
_USER_AGENT = "HNSearch-Bot/1.0 (+https://github.com/your-org/hn-search)"

SKIP_DOMAINS: frozenset[str] = frozenset(
    {
        "twitter.com", "x.com", "t.co",
        "youtube.com", "youtu.be",
        "instagram.com", "facebook.com",
        "tiktok.com", "reddit.com",
        "linkedin.com",
    }
)

SKIP_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".mp4", ".mp3", ".zip", ".gz", ".tar", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
)


# ---------------------------------------------------------------------------
# IP safety
# ---------------------------------------------------------------------------

def _is_safe_host(hostname: str) -> bool:
    """Return True only if the hostname resolves to a public, routable IP."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for *_, sockaddr in infos:
        raw = sockaddr[0]
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            return False
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            return False
    return bool(infos)


def _validate_url(url: str) -> tuple[str, str]:
    """
    Parse and validate URL.  Returns (url, hostname) or raises ValueError.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Scheme not allowed: {parsed.scheme!r}")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("Missing hostname")
    # domain skip list
    bare = hostname.removeprefix("www.")
    if bare in SKIP_DOMAINS or hostname in SKIP_DOMAINS:
        raise ValueError(f"Domain in skip list: {hostname}")
    # extension skip
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        raise ValueError(f"Skipped extension: {parsed.path}")
    if not _is_safe_host(hostname):
        raise ValueError(f"Hostname resolves to a private/reserved IP: {hostname}")
    return url, hostname


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------

def _fetch_robots_sync(base_url: str) -> RobotFileParser | None:
    rp = RobotFileParser()
    rp.set_url(urljoin(base_url, "/robots.txt"))
    try:
        rp.read()
        return rp
    except Exception:
        return None


def _robots_allowed(hostname: str, base_url: str, url: str) -> bool:
    if hostname not in _ROBOTS_CACHE:
        _ROBOTS_CACHE[hostname] = _fetch_robots_sync(base_url)
    rp = _ROBOTS_CACHE[hostname]
    if rp is None:
        return True
    return rp.can_fetch(_USER_AGENT, url)


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def _host_sem(hostname: str) -> asyncio.Semaphore:
    if hostname not in _HOST_SEMS:
        _HOST_SEMS[hostname] = asyncio.Semaphore(2)
    return _HOST_SEMS[hostname]


async def fetch_article(url: str) -> str:
    """
    Fetch article HTML safely.  Returns raw HTML text.
    Raises ValueError for policy violations, aiohttp errors for network issues.
    """
    url, hostname = _validate_url(url)
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if not _robots_allowed(hostname, base_url, url):
        raise ValueError(f"Blocked by robots.txt: {url}")

    timeout = aiohttp.ClientTimeout(connect=_CONNECT_TIMEOUT, sock_read=_READ_TIMEOUT)
    headers = {"User-Agent": _USER_AGENT}

    async with _GLOBAL_SEM, _host_sem(hostname):
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            current_url = url
            for hop in range(_MAX_REDIRECTS + 1):
                resp = await session.get(
                    current_url,
                    allow_redirects=False,
                    max_line_size=8190,
                )
                if resp.status in (301, 302, 303, 307, 308):
                    if hop == _MAX_REDIRECTS:
                        raise ValueError("Too many redirects")
                    location = resp.headers.get("Location", "")
                    if not location:
                        raise ValueError("Redirect with no Location header")
                    next_url = urljoin(current_url, location)
                    next_url, hostname = _validate_url(next_url)  # re-check each hop
                    parsed = urlparse(next_url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    if not _robots_allowed(hostname, base_url, next_url):
                        raise ValueError(f"Redirect target blocked by robots.txt: {next_url}")
                    current_url = next_url
                    await resp.release()
                    continue

                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info, resp.history, status=resp.status
                    )

                ct = resp.headers.get("Content-Type", "")
                if "html" not in ct.lower():
                    raise ValueError(f"Non-HTML content-type: {ct!r}")

                # Stream with hard cap
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.content.iter_chunked(32768):
                    total += len(chunk)
                    if total > _MAX_BODY:
                        raise ValueError("Response body exceeds size cap")
                    chunks.append(chunk)

                encoding = resp.charset or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace")

    raise ValueError("Fetch loop exited without response")  # unreachable
