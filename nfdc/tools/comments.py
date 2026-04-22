"""MCP tools for retrieving comments on a planning application.

This module exposes two tools:

- ``get_public_comments`` — public (neighbour) comments, paginated at 10 per page.
- ``get_consultee_comments`` — statutory consultee responses, paginated at 5 per page.

Both tools are registered on the MCP server via the :func:`register` function.
"""

from bs4 import BeautifulSoup
from fastmcp import FastMCP

from nfdc.constants import DETAILS_URL
from nfdc.http import make_client
from nfdc.parsers import (
    parse_comment_statistics,
    parse_consultee_comments,
    parse_pagination,
    parse_public_comments,
)


def _build_url(tab: str, key_val: str, page: int, pager_param: str) -> str:
    """Construct the portal URL for a paginated comments tab.

    Args:
        tab: The ``activeTab`` value, e.g. ``"neighbourComments"``.
        key_val: The portal's internal application identifier.
        page: The requested page number (1-indexed).
        pager_param: The query parameter name used by the portal's pager,
            e.g. ``"neighbourCommentsPager.page"``.

    Returns:
        The full URL string, including the page parameter when ``page > 1``.
    """
    url = f"{DETAILS_URL}?activeTab={tab}&keyVal={key_val}"
    if page > 1:
        url += f"&{pager_param}={page}"
    return url


def register(mcp: FastMCP) -> None:
    """Register the public and consultee comment tools on the given MCP server.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server instance to attach the tools to.
    """

    @mcp.tool
    def get_public_comments(key_val: str, page: int = 1) -> dict:
        """Get public (neighbour) comments for a planning application.

        Retrieves comments submitted by members of the public (typically local
        residents) for the given application.  Results are paginated at 10
        comments per page.

        Args:
            key_val: The portal's internal application identifier returned by
                ``search_applications``, e.g. ``"_NEWFO_DCAPR_223030"``.
            page: Page number to retrieve.  Defaults to ``1``.
                Each page contains up to 10 comments.

        Returns:
            A dictionary with the following keys:

            - ``comments`` (list[dict]): Comments on this page.  Each entry
              contains:

              - ``name`` (str): Commenter's full name.
              - ``stance`` (str): Stated position, e.g. ``"Objects"`` or
                ``"Supports"``.  Empty string if not found.
              - ``date`` (str): Submission date, e.g. ``"Wed 15 Apr 2026"``.
              - ``text`` (str): Full body of the comment.

            - ``statistics`` (dict): Headline figures extracted from the page,
              with keys ``total_consulted``, ``comments_received``,
              ``objections`` and ``supporting`` (all as strings).
            - ``page`` (int): The current page number.
            - ``total_pages`` (int): Total number of pages available.
            - ``url`` (str): The URL that was fetched.

        Raises:
            httpx.HTTPStatusError: If the portal returns a non-2xx response.
        """
        url = _build_url(
            "neighbourComments", key_val, page, "neighbourCommentsPager.page"
        )
        client = make_client()
        resp = client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        pagination = parse_pagination(soup)

        return {
            "comments": parse_public_comments(soup),
            "statistics": parse_comment_statistics(soup),
            "page": page,
            "total_pages": pagination["total_pages"],
            "url": url,
        }

    @mcp.tool
    def get_consultee_comments(key_val: str, page: int = 1) -> dict:
        """Get statutory consultee comments for a planning application.

        Retrieves responses from organisations formally consulted on the
        application — such as the Environment Agency, Natural England, HCC
        Highways, parish councils and internal NFDC teams.  Results are
        paginated at 5 consultees per page.

        Note:
            Many consultee responses are filed as documents rather than inline
            text.  In those cases the ``text`` field will contain
            ``"Comment can be viewed under Related Documents"`` and the actual
            response can be found via ``get_documents``.

        Args:
            key_val: The portal's internal application identifier returned by
                ``search_applications``, e.g. ``"_NEWFO_DCAPR_223030"``.
            page: Page number to retrieve.  Defaults to ``1``.
                Each page contains up to 5 consultee entries.

        Returns:
            A dictionary with the following keys:

            - ``comments`` (list[dict]): Consultee entries on this page.
              Each entry contains:

              - ``consultee`` (str): Name of the consultee organisation.
              - ``consultation_date`` (str): Date of consultation, or empty
                string.
              - ``text`` (str): Comment text, or
                ``"Comment can be viewed under Related Documents"``.

            - ``page`` (int): The current page number.
            - ``total_pages`` (int): Total number of pages available.
            - ``url`` (str): The URL that was fetched.

        Raises:
            httpx.HTTPStatusError: If the portal returns a non-2xx response.
        """
        url = _build_url(
            "consulteeComments", key_val, page, "consulteeCommentsPager.page"
        )
        client = make_client()
        resp = client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        pagination = parse_pagination(soup)

        return {
            "comments": parse_consultee_comments(soup),
            "page": page,
            "total_pages": pagination["total_pages"],
            "url": url,
        }
