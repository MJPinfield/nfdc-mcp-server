"""HTTP client utilities for the NFDC planning MCP server.

Provides a factory for creating pre-configured ``httpx.Client`` instances
and a helper that obtains the session cookie and CSRF token required before
submitting any search form POST.
"""

import httpx
from bs4 import BeautifulSoup

from nfdc.constants import HEADERS, SEARCH_PAGE_URL, SSL_VERIFY


def make_client(timeout: int = 30) -> httpx.Client:
    """Create a pre-configured synchronous HTTP client.

    The client follows redirects automatically, sends the standard browser
    headers defined in :mod:`nfdc.constants`, and has TLS verification
    disabled to work around the NFDC server's misconfigured certificate chain.

    Args:
        timeout: Request timeout in seconds.  Defaults to ``30``.

    Returns:
        A ready-to-use :class:`httpx.Client` instance.
    """
    return httpx.Client(
        headers=HEADERS,
        follow_redirects=True,
        timeout=timeout,
        verify=SSL_VERIFY,
    )


def get_session_and_csrf() -> tuple[httpx.Client, str]:
    """Obtain a session cookie and CSRF token from the search page.

    The NFDC planning portal requires both a valid session cookie (set by the
    server on first visit) and a matching ``_csrf`` hidden-field value before
    it will accept a search POST.  This function GETs the search page,
    extracts the token and returns the client (which now holds the session
    cookie in its cookie jar) along with the token string.

    Returns:
        A tuple of ``(client, csrf_token)`` where *client* is an
        :class:`httpx.Client` that already has the session cookie attached
        and *csrf_token* is the string value to embed in the POST body.

    Raises:
        RuntimeError: If the CSRF token input element cannot be found on the
            search page, which would indicate an unexpected change to the
            portal's HTML.
        httpx.HTTPStatusError: If the search page returns a non-2xx status.
    """
    client = make_client()
    resp = client.get(SEARCH_PAGE_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    csrf_input = soup.find("input", {"name": "_csrf"})
    if not csrf_input:
        raise RuntimeError(
            "Could not find CSRF token on the NFDC search page. "
            "The portal HTML may have changed."
        )

    return client, csrf_input["value"]
