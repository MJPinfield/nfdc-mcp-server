"""Shared HTML parsing utilities for the NFDC planning MCP server.

All functions in this module accept a :class:`bs4.BeautifulSoup` object
(already parsed) and return plain Python dicts or lists.  Nothing in here
makes any network requests.
"""

import re
from typing import Optional

from bs4 import BeautifulSoup


def extract_key_val(url: str) -> Optional[str]:
    """Extract the ``keyVal`` query parameter from a URL string.

    The ``keyVal`` is the portal's internal identifier for a planning
    application (e.g. ``_NEWFO_DCAPR_223030``) and is required by all
    detail-tab endpoints.

    Args:
        url: Any URL that may contain a ``keyVal=`` query parameter.

    Returns:
        The extracted key value string, or ``None`` if the parameter is not
        present in the URL.

    Example:
        >>> extract_key_val(
        ...     "https://planning.newforest.gov.uk/online-applications/"
        ...     "applicationDetails.do?activeTab=summary&keyVal=_NEWFO_DCAPR_223030"
        ... )
        '_NEWFO_DCAPR_223030'
    """
    match = re.search(r"keyVal=([^&]+)", url)
    return match.group(1) if match else None


def parse_table(soup: BeautifulSoup) -> dict[str, str]:
    """Parse a two-column ``<table>`` into a flat key/value dictionary.

    The NFDC portal uses simple ``<th>Label</th><td>Value</td>`` tables for
    most structured data (summary, further information, important dates).
    This function collects every row that has at least two cells and returns
    the result as a ``{label: value}`` dict.  Rows with an empty first cell
    are skipped.

    Args:
        soup: A parsed BeautifulSoup document or tag to search within.

    Returns:
        A dictionary mapping each row's label text to its value text.
        Both keys and values are stripped of leading/trailing whitespace.

    Example:
        >>> data = parse_table(soup)
        >>> data["Reference"]
        '25/10114'
        >>> data["Status"]
        'Registered'
    """
    data: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.select("th, td")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if key:
                data[key] = value
    return data


def parse_public_comments(soup: BeautifulSoup) -> list[dict]:
    """Parse public (neighbour) comment blocks from an application comments page.

    The portal renders each comment as a ``<div class="comment">`` containing
    a ``.consultationName`` span for the commenter's name, and free-form text
    that includes the stance (e.g. ``(Objects)``) and submission date.

    Args:
        soup: A parsed BeautifulSoup document for the ``neighbourComments`` tab.

    Returns:
        A list of comment dictionaries, each containing:

        - ``name`` (str): Full name of the commenter.
        - ``stance`` (str): Stated position, e.g. ``"Objects"`` or ``"Supports"``.
          Empty string if not determinable.
        - ``date`` (str): Comment submission date as a string, e.g. ``"Wed 15 Apr 2026"``.
          Empty string if not found.
        - ``text`` (str): The body of the comment.
    """
    comments: list[dict] = []

    for comment_div in soup.select(".comment"):
        name_el = comment_div.select_one(".consultationName")
        stance_el = comment_div.select_one(".consultationStatus, .stance")
        date_el = comment_div.select_one(".consultationDate, .date")
        text_el = comment_div.select_one(".consultationText, .commentText, p")

        raw_text = comment_div.get_text(" ", strip=True)

        stance_match = re.search(
            r"\((Objects?|Supports?|Neutral|No objection)\)", raw_text, re.I
        )
        date_match = re.search(
            r"Comment submitted date:\s*(\w+ \d+ \w+ \d+)", raw_text
        )

        comment: dict = {
            "name": name_el.get_text(strip=True) if name_el else "",
            "stance": (
                stance_el.get_text(strip=True)
                if stance_el
                else (stance_match.group(1) if stance_match else "")
            ),
            "date": (
                date_el.get_text(strip=True)
                if date_el
                else (date_match.group(1) if date_match else "")
            ),
            "text": "",
        }

        if date_match:
            comment["text"] = raw_text[date_match.end():].strip()
        elif text_el:
            comment["text"] = text_el.get_text(strip=True)

        comments.append(comment)

    return comments


def parse_consultee_comments(soup: BeautifulSoup) -> list[dict]:
    """Parse statutory consultee comment blocks from an application comments page.

    Consultee comments differ structurally from public comments: the
    organisation name is in an ``<h2>`` and each response is wrapped in a
    ``<div class="commentText">`` block.  Many consultee responses are held
    as documents rather than inline text, in which case the text field will
    say so.

    Args:
        soup: A parsed BeautifulSoup document for the ``consulteeComments`` tab.

    Returns:
        A list of comment dictionaries, each containing:

        - ``consultee`` (str): Name of the consultee organisation.
        - ``consultation_date`` (str): Date of consultation, or empty string.
        - ``text`` (str): Comment text, or
          ``"Comment can be viewed under Related Documents"`` if the response
          is filed as a document rather than inline text.
    """
    comments: list[dict] = []

    for comment_div in soup.select(".comment"):
        name_el = comment_div.select_one("h2, .consultationName")
        consultee_name = name_el.get_text(strip=True) if name_el else ""

        comment_blocks = comment_div.select(".commentText")
        if comment_blocks:
            for block in comment_blocks:
                date_el = block.select_one("h3")
                if date_el and "Consultation Date" in date_el.get_text():
                    date_el.extract()

                block_text = block.get_text(" ", strip=True)
                is_document_ref = "Comment can be viewed" in block_text

                comments.append(
                    {
                        "consultee": consultee_name,
                        "consultation_date": (
                            ""
                            if is_document_ref
                            else block_text
                        ),
                        "text": (
                            "Comment can be viewed under Related Documents"
                            if is_document_ref
                            else block_text
                        ),
                    }
                )
        else:
            raw_text = comment_div.get_text(" ", strip=True)
            comments.append(
                {
                    "consultee": consultee_name,
                    "consultation_date": "",
                    "text": (
                        "Comment can be viewed under Related Documents"
                        if "Comment can be viewed" in raw_text
                        else raw_text
                    ),
                }
            )

    return comments


def parse_comment_statistics(soup: BeautifulSoup) -> dict[str, str]:
    """Extract headline comment statistics from the public comments page.

    The NFDC portal displays a summary bar such as::

        Total Consulted: 1341  Comments Received: 971  Objections: 966  Supporting: 3

    This function locates those figures via regex and returns them as strings.

    Args:
        soup: A parsed BeautifulSoup document for the ``neighbourComments`` tab.

    Returns:
        A dictionary with keys ``total_consulted``, ``comments_received``,
        ``objections`` and ``supporting``.  Any value not found on the page
        is omitted from the returned dict.
    """
    stats: dict[str, str] = {}
    page_text = soup.get_text(" ")

    patterns = [
        (r"Total Consulted:\s*([\d,]+)", "total_consulted"),
        (r"Comments Received:\s*([\d,]+)", "comments_received"),
        (r"Objections:\s*([\d,]+)", "objections"),
        (r"Supporting:\s*([\d,]+)", "supporting"),
    ]
    for pattern, key in patterns:
        match = re.search(pattern, page_text)
        if match:
            stats[key] = match.group(1).replace(",", "")

    return stats


def parse_pagination(soup: BeautifulSoup) -> dict[str, int]:
    """Determine the total number of pages from a paginated results page.

    The portal's pager renders individual page-number links whose ``href``
    attributes contain a ``Pager.page=N`` parameter.  The highest ``N`` found
    is taken as the total page count.

    Args:
        soup: A parsed BeautifulSoup document containing pagination links.

    Returns:
        A dictionary with keys:

        - ``total_pages`` (int): Highest page number found in pager links,
          or ``1`` if no pager links are present.
        - ``current_page`` (int): Always ``1`` (the portal does not mark the
          current page in a way that is easily machine-readable).
    """
    page_numbers: set[int] = set()
    for link in soup.select("a[href*='Pager.page=']"):
        match = re.search(r"Pager\.page=(\d+)", link["href"])
        if match:
            page_numbers.add(int(match.group(1)))

    return {
        "total_pages": max(page_numbers) if page_numbers else 1,
        "current_page": 1,
    }


def parse_document_types(soup: BeautifulSoup) -> list[str]:
    """Extract the available document type filter options from the documents tab.

    The portal renders a ``<select id="documentType">`` dropdown.  This
    function returns the human-readable labels for all non-sentinel options
    (i.e. everything except "Show All", which has ``value="0"``).

    Args:
        soup: A parsed BeautifulSoup document for the base ``documents`` tab
            URL (without ordering parameters — the server only includes the
            full option list on the bare URL).

    Returns:
        A list of document type label strings such as ``["Plans",
        "Applications Processing", "Consultee Comment", ...]``.
        Returns an empty list if the dropdown is not found.
    """
    type_select = soup.select_one("select#documentType, select[name='documentType']")
    if not type_select:
        return []

    return [
        option.get_text(strip=True)
        for option in type_select.select("option")
        if option.get("value", "") != "0" and option.get_text(strip=True)
    ]


def parse_document_rows(soup: BeautifulSoup) -> list[dict]:
    """Parse all document rows from the documents tab table.

    The portal renders documents in a flat ``<table>`` with no ``<tbody>``
    element.  The column order is::

        [checkbox] [date] [type] [measure] [drawing_number] [description] [view]

    This function returns every data row (skipping the header row) as a dict.

    Args:
        soup: A parsed BeautifulSoup document for the ``documents`` tab.

    Returns:
        A list of document dictionaries, each containing:

        - ``date`` (str): Date the document was published.
        - ``type`` (str): Document type category.
        - ``drawing_number`` (str): Drawing reference number (often empty).
        - ``description`` (str): Human-readable document name.
        - ``download_url`` (str): Absolute URL to the document file.
    """
    _HEADER_TEXTS = {
        "Date Published", "Document Type", "Drawing Number",
        "Description", "Measure", "View",
    }

    table = soup.find("table")
    if not table:
        return []

    documents: list[dict] = []

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""

        # Skip the header row and any row without a date value
        if not date_text or date_text in _HEADER_TEXTS:
            continue

        link = row.find("a", href=lambda h: h and "/files/" in h)
        download_url = ""
        if link:
            href = link["href"]
            download_url = (
                f"https://planning.newforest.gov.uk{href}"
                if href.startswith("/")
                else href
            )

        documents.append(
            {
                "date": date_text,
                "type": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                "drawing_number": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                "description": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                "download_url": download_url,
            }
        )

    return documents
