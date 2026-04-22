"""MCP tool for retrieving documents associated with a planning application.

This module exposes a single tool, ``get_documents``, which fetches the full
document list from the NFDC planning portal and returns a paginated, optionally
filtered slice.

The portal returns all documents in a single HTML response (no server-side
pagination), so filtering and pagination are applied client-side after parsing.
"""

import math

from bs4 import BeautifulSoup
from fastmcp import FastMCP

from nfdc.constants import DETAILS_URL, DOCUMENTS_PAGE_SIZE
from nfdc.http import make_client
from nfdc.parsers import parse_document_rows, parse_document_types


def _fetch_document_types(key_val: str) -> list[str]:
    """Fetch the available document type options from the base documents tab.

    The portal only includes the full ``<select>`` option list on the bare
    documents URL (without ordering parameters).  A separate request is
    therefore made here to retrieve them reliably.

    Args:
        key_val: The portal's internal application identifier.

    Returns:
        A list of document type label strings (e.g. ``["Plans",
        "Applications Processing", ...]``).  Returns an empty list if
        the dropdown cannot be found.

    Raises:
        httpx.HTTPStatusError: If the portal returns a non-2xx response.
    """
    client = make_client(timeout=60)
    resp = client.get(f"{DETAILS_URL}?activeTab=documents&keyVal={key_val}")
    resp.raise_for_status()
    return parse_document_types(BeautifulSoup(resp.text, "lxml"))


def _fetch_all_documents(key_val: str, order_by: str, order_direction: str) -> list[dict]:
    """Fetch and parse every document row for an application.

    Sends a single GET request for the documents tab with the requested
    ordering applied.  All rows are returned; filtering and pagination happen
    in the calling code.

    Args:
        key_val: The portal's internal application identifier.
        order_by: Column to sort by.  Accepted values are ``"date"``,
            ``"documentType"``, ``"drawingNumber"`` and ``"description"``.
        order_direction: Sort direction — ``"ascending"`` or ``"descending"``.

    Returns:
        A list of all parsed document dicts for the application.

    Raises:
        httpx.HTTPStatusError: If the portal returns a non-2xx response.
    """
    url = (
        f"{DETAILS_URL}?activeTab=documents&keyVal={key_val}"
        f"&documentOrdering.orderBy={order_by}"
        f"&documentOrdering.orderDirection={order_direction}"
    )
    client = make_client(timeout=60)
    resp = client.get(url)
    resp.raise_for_status()
    return parse_document_rows(BeautifulSoup(resp.text, "lxml"))


def register(mcp: FastMCP) -> None:
    """Register the ``get_documents`` tool on the given MCP server.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server instance to attach the tool to.
    """

    @mcp.tool
    def get_documents(
        key_val: str,
        document_type: str = "Show All",
        page: int = 1,
        order_by: str = "date",
        order_direction: str = "descending",
    ) -> dict:
        """Get documents associated with a planning application.

        The NFDC portal returns all documents for an application in a single
        HTML page.  This tool parses that page, optionally filters by document
        type, and returns a paginated slice of 25 documents per call.

        Args:
            key_val: The portal's internal application identifier returned by
                ``search_applications``, e.g. ``"_NEWFO_DCAPR_223030"``.
            document_type: Filter results to a single document type.  Pass
                ``"Show All"`` (the default) to return all types.  Valid
                values are listed in the ``available_types`` field of the
                response and typically include ``"Plans"``,
                ``"Applications Processing"``, ``"Consultee Comment"``,
                ``"Reports"``, ``"Representees"``,
                ``"Submitted Applications"`` and ``"Superseded Plans"``.
            page: Page number to return.  Defaults to ``1``.
                Each page contains up to 25 documents.
            order_by: Field to sort by.  One of ``"date"``,
                ``"documentType"``, ``"drawingNumber"`` or
                ``"description"``.  Defaults to ``"date"``.
            order_direction: Sort direction — ``"ascending"`` or
                ``"descending"``.  Defaults to ``"descending"`` so the most
                recent documents appear first.

        Returns:
            A dictionary with the following keys:

            - ``documents`` (list[dict]): Up to 25 documents on the requested
              page.  Each entry contains:

              - ``date`` (str): Date the document was published.
              - ``type`` (str): Document type category.
              - ``drawing_number`` (str): Drawing reference (often empty).
              - ``description`` (str): Human-readable document name.
              - ``download_url`` (str): Absolute URL to view or download
                the document.

            - ``available_types`` (list[str]): All document type options
              available for this application (can be passed back as
              ``document_type`` on subsequent calls).
            - ``page`` (int): The current page number.
            - ``total_pages`` (int): Total number of pages at 25 per page.
            - ``total_count`` (int): Total number of documents matching the
              current filter.
            - ``url`` (str): The portal URL used to retrieve the document list.

        Raises:
            httpx.HTTPStatusError: If any portal request returns a non-2xx
                response.
        """
        available_types = _fetch_document_types(key_val)
        all_documents = _fetch_all_documents(key_val, order_by, order_direction)

        # Apply client-side type filter
        if document_type != "Show All":
            all_documents = [d for d in all_documents if d["type"] == document_type]

        total_count = len(all_documents)
        total_pages = max(1, math.ceil(total_count / DOCUMENTS_PAGE_SIZE))

        start = (page - 1) * DOCUMENTS_PAGE_SIZE
        end = start + DOCUMENTS_PAGE_SIZE

        return {
            "documents": all_documents[start:end],
            "available_types": available_types,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "url": (
                f"{DETAILS_URL}?activeTab=documents&keyVal={key_val}"
                f"&documentOrdering.orderBy={order_by}"
                f"&documentOrdering.orderDirection={order_direction}"
            ),
        }
