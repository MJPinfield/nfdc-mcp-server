"""Shared constants for the NFDC planning MCP server.

Centralises all URLs, HTTP headers and configuration flags so they
are defined in exactly one place and imported wherever needed.
"""

BASE_URL = "https://planning.newforest.gov.uk/online-applications"

SEARCH_PAGE_URL = f"{BASE_URL}/search.do?action=simple&searchType=Application"
"""URL of the simple search form (GET).  Used to obtain a session cookie and CSRF token."""

SEARCH_RESULTS_URL = f"{BASE_URL}/simpleSearchResults.do?action=firstPage"
"""Endpoint that accepts the search POST and returns results."""

DETAILS_URL = f"{BASE_URL}/applicationDetails.do"
"""Base URL for all application-detail tabs.  Append ``?activeTab=<tab>&keyVal=<key>``."""

HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Origin": "https://planning.newforest.gov.uk",
    "Referer": SEARCH_PAGE_URL,
}
"""HTTP request headers sent with every request to mimic a real browser."""

# The NFDC server serves a certificate signed by DigiCert Global G2 but does
# not include that intermediate CA in the chain it sends.  Python's ssl module
# rejects the handshake as a result.  Because this is a well-known public
# government portal we accept the risk and disable verification.
SSL_VERIFY: bool = False
"""Whether to verify TLS certificates.  Disabled due to a server-side chain misconfiguration."""

DOCUMENTS_PAGE_SIZE: int = 25
"""Number of documents returned per page when paginating the document list."""
