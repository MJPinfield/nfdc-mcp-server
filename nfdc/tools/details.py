"""MCP tool for retrieving full details of a planning application.

This module exposes a single tool, ``get_application_details``, which fetches
the three detail tabs (summary, further information, important dates) for a
given application and returns them as a single consolidated response.
"""

from bs4 import BeautifulSoup
from fastmcp import FastMCP

from nfdc.constants import DETAILS_URL
from nfdc.http import make_client
from nfdc.parsers import parse_table


def _fetch_tab(key_val: str, tab: str) -> dict[str, str]:
    """Fetch a single detail tab and return its table data.

    Args:
        key_val: The portal's internal application identifier,
            e.g. ``"_NEWFO_DCAPR_223030"``.
        tab: The ``activeTab`` query parameter value, e.g. ``"summary"``,
            ``"details"``, or ``"dates"``.

    Returns:
        A flat ``{label: value}`` dictionary parsed from the two-column table
        on the requested tab.

    Raises:
        httpx.HTTPStatusError: If the portal returns a non-2xx response.
    """
    client = make_client()
    resp = client.get(f"{DETAILS_URL}?activeTab={tab}&keyVal={key_val}")
    resp.raise_for_status()
    return parse_table(BeautifulSoup(resp.text, "lxml"))


def _extract_progress(soup: BeautifulSoup) -> str:
    """Extract the current lifecycle stage from the application summary page.

    The portal renders a horizontal progress bar with the active stage marked
    in bold.  This helper returns the text of the active stage, or an empty
    string if none is found.

    Args:
        soup: Parsed BeautifulSoup of the application summary tab.

    Returns:
        The label of the current progress stage (e.g. ``"Recommendation and/or
        Committee"``), or an empty string if the element cannot be located.
    """
    active = soup.select_one(
        ".progressBar .current, .progressBar .active, .progressBar strong"
    )
    return active.get_text(strip=True) if active else ""


def register(mcp: FastMCP) -> None:
    """Register the ``get_application_details`` tool on the given MCP server.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server instance to attach the tool to.
    """

    @mcp.tool
    def get_application_details(key_val: str) -> dict:
        """Get the full details of a planning application.

        Fetches the Summary, Further Information and Important Dates tabs from
        the NFDC planning portal and returns all fields in a single response.
        The ``key_val`` can be obtained by calling ``search_applications`` first.

        Args:
            key_val: The portal's internal application identifier returned by
                ``search_applications``, e.g. ``"_NEWFO_DCAPR_223030"``.

        Returns:
            A dictionary with the following keys:

            - ``summary`` (dict): Core application fields such as ``Reference``,
              ``Address``, ``Proposal``, ``Status``, ``Application Received``
              and ``Application Validated``.
            - ``further_information`` (dict): Additional fields including
              ``Application Type``, ``Case Officer``, ``Parish``, ``Ward``,
              ``Applicant Name``, ``Applicant Address`` and
              ``Environmental Assessment Requested``.
            - ``important_dates`` (dict): Key dates such as
              ``Application Validated Date``, ``Standard Consultation Date``,
              ``Standard Consultation Expiry Date`` and
              ``Actual Committee Date``.
            - ``progress`` (str): Current stage label from the lifecycle
              progress bar (e.g. ``"Recommendation and/or Committee"``).
              Empty string if the stage cannot be determined.
            - ``url`` (str): Public URL for the application summary page.

        Raises:
            httpx.HTTPStatusError: If any tab request returns a non-2xx response.
        """
        client = make_client()

        # Summary tab — also need the parsed soup to extract the progress bar
        resp = client.get(f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}")
        resp.raise_for_status()
        summary_soup = BeautifulSoup(resp.text, "lxml")

        return {
            "summary": parse_table(summary_soup),
            "further_information": _fetch_tab(key_val, "details"),
            "important_dates": _fetch_tab(key_val, "dates"),
            "progress": _extract_progress(summary_soup),
            "url": f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}",
        }
