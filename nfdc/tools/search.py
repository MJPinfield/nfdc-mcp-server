"""MCP tool for searching New Forest District Council planning applications.

This module exposes a single tool, ``search_applications``, which submits a
POST search to the NFDC planning portal and returns a normalised list of
matching applications.
"""

import re

from bs4 import BeautifulSoup
from fastmcp import FastMCP

from nfdc.constants import DETAILS_URL, SEARCH_RESULTS_URL
from nfdc.http import get_session_and_csrf
from nfdc.parsers import extract_key_val, parse_table


def _parse_single_result(soup: BeautifulSoup, resp_url: str) -> dict:
    """Parse the page when the search redirected directly to one application.

    The portal skips the results list and lands on the application summary
    tab when the query matches exactly one application.  This helper handles
    that case by extracting the data directly from the summary page.

    Args:
        soup: Parsed BeautifulSoup of the application summary page.
        resp_url: The final URL after any redirects, used as a fallback when
            the ``keyVal`` cannot be found in an anchor tag.

    Returns:
        A single-element list containing the application dict with keys
        ``reference``, ``address``, ``proposal``, ``status``, ``key_val``
        and ``url``.
    """
    key_val = None
    for anchor in soup.select("a[href*='keyVal=']"):
        key_val = extract_key_val(anchor["href"])
        if key_val:
            break

    table_data = parse_table(soup)

    # Fall back to the h2 text if the table doesn't contain a Reference row
    app_ref = table_data.get("Reference", "")
    if not app_ref:
        ref_el = soup.select_one("h2")
        if ref_el:
            app_ref = ref_el.get_text(strip=True)

    return {
        "reference": app_ref,
        "address": table_data.get("Address", ""),
        "proposal": table_data.get("Proposal", ""),
        "status": table_data.get("Status", ""),
        "key_val": key_val,
        "url": (
            f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}"
            if key_val
            else resp_url
        ),
    }


def _parse_multiple_results(soup: BeautifulSoup) -> list[dict]:
    """Parse a standard search results list page.

    Args:
        soup: Parsed BeautifulSoup of the results list page.

    Returns:
        A list of application dicts, each with keys ``reference``,
        ``address``, ``proposal``, ``status``, ``key_val`` and ``url``.
        Rows that do not contain an ``applicationDetails`` link are skipped.
    """
    results: list[dict] = []

    items = soup.select("li.searchresult, .search-result, .applicationRow")
    if not items:
        items = soup.select("table.searchresults tbody tr, #searchresults tbody tr")

    for item in items:
        link = item.select_one("a[href*='applicationDetails']")
        if not link:
            continue

        key_val = extract_key_val(link["href"])

        meta = item.select_one(".address, .metaData")
        desc = item.select_one(".description, .proposal")
        status_el = item.select_one(".status")

        results.append(
            {
                "reference": link.get_text(strip=True),
                "address": meta.get_text(strip=True) if meta else "",
                "proposal": desc.get_text(strip=True) if desc else "",
                "status": status_el.get_text(strip=True) if status_el else "",
                "key_val": key_val,
                "url": f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}",
            }
        )

    return results


def register(mcp: FastMCP) -> None:
    """Register the ``search_applications`` tool on the given MCP server.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server instance to attach the tool to.
    """

    @mcp.tool
    def search_applications(
        query: str,
        status: str = "All",
    ) -> dict:
        """Search for planning applications on the New Forest District Council website.

        Submits a simple search POST to the NFDC planning portal and returns a
        normalised list of matching applications.  When the query matches
        exactly one application the portal redirects to that application's
        summary page directly; this tool handles both cases transparently.

        Args:
            query: Search term.  Accepts a reference number (e.g. ``25/10114``),
                a postcode (e.g. ``BH24 3PG``), a keyword, or a single line of
                an address.
            status: Filter results by application status.  One of ``"All"``,
                ``"Current"``, ``"Decided"``, ``"Withdrawn"``, or ``"Appeal"``.
                Defaults to ``"All"``.

        Returns:
            A dictionary with the following keys:

            - ``results`` (list[dict]): Matching applications.  Each entry
              contains ``reference``, ``address``, ``proposal``, ``status``,
              ``key_val`` (internal portal ID used by all other tools) and
              ``url`` (link to the public application page).
            - ``total_count`` (int): Number of results returned.
            - ``message`` (str): Any warning or error message shown by the
              portal (e.g. *"Too many results found"*).  Empty string when
              the search succeeded normally.

        Raises:
            httpx.HTTPStatusError: If the portal returns a non-2xx response.
            RuntimeError: If the CSRF token cannot be found on the search page.
        """
        client, csrf = get_session_and_csrf()

        form_data = {
            "_csrf": csrf,
            "searchType": "Application",
            "searchCriteria.caseStatus": status,
            "searchCriteria.simpleSearchString": query,
            "searchCriteria.simpleSearch": "true",
        }

        resp = client.post(SEARCH_RESULTS_URL, data=form_data)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Surface any portal-level warning/error messages
        message = ""
        error_box = soup.select_one(".errorMsg, .warningMsg, .errors li, .messages li")
        if error_box:
            message = error_box.get_text(strip=True)

        # Detect whether we landed on a single-application summary page
        h1 = soup.select_one("h1")
        if h1 and "Application Summary" in h1.get_text():
            result = _parse_single_result(soup, str(resp.url))
            return {"results": [result], "total_count": 1, "message": message}

        results = _parse_multiple_results(soup)
        return {"results": results, "total_count": len(results), "message": message}
