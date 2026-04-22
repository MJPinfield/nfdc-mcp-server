"""
New Forest District Council Planning Applications MCP Server

Provides tools to search and retrieve planning application information
from https://planning.newforest.gov.uk/online-applications/
"""

import math
import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from fastmcp import FastMCP

BASE_URL = "https://planning.newforest.gov.uk/online-applications"
SEARCH_PAGE_URL = f"{BASE_URL}/search.do?action=simple&searchType=Application"
SEARCH_RESULTS_URL = f"{BASE_URL}/simpleSearchResults.do?action=firstPage"
DETAILS_URL = f"{BASE_URL}/applicationDetails.do"

# Common browser headers to avoid bot detection
HEADERS = {
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

# The NFDC server has a misconfigured TLS chain (missing intermediate DigiCert G2 cert).
# SSL verification is disabled to work around this server-side issue.
# The site is a known public government portal so the risk is accepted.
SSL_VERIFY = False

mcp = FastMCP(
    name="NFDC Planning",
    instructions=(
        "Tools for searching and retrieving planning application information "
        "from New Forest District Council. Use search_applications to find "
        "applications by reference number, keyword, postcode or address. "
        "Then use the other tools to get details, comments and documents."
    ),
)


def _get_session_and_csrf() -> tuple[httpx.Client, str]:
    """Create a session and fetch a CSRF token from the search page."""
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=SSL_VERIFY)
    resp = client.get(SEARCH_PAGE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    csrf_input = soup.find("input", {"name": "_csrf"})
    if not csrf_input:
        raise RuntimeError("Could not find CSRF token on search page")
    return client, csrf_input["value"]


def _extract_key_val(url: str) -> Optional[str]:
    """Extract the keyVal parameter from a URL."""
    match = re.search(r"keyVal=([^&]+)", url)
    return match.group(1) if match else None


def _parse_table(soup: BeautifulSoup) -> dict[str, str]:
    """Parse a two-column table into a dict."""
    data = {}
    for row in soup.select("table tr"):
        cells = row.select("th, td")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if key:
                data[key] = value
    return data


def _parse_comments(soup: BeautifulSoup) -> list[dict]:
    """Parse comment blocks from a page."""
    comments = []
    for comment_div in soup.select(".comment"):
        name_el = comment_div.select_one(".consultationName")
        stance_el = comment_div.select_one(".consultationStatus, .stance")
        date_el = comment_div.select_one(".consultationDate, .date")
        text_el = comment_div.select_one(".consultationText, .commentText, p")

        # Fall back to text parsing if structured elements not found
        raw_text = comment_div.get_text(" ", strip=True)

        # Try to find stance in parentheses pattern like "(Objects)"
        stance_match = re.search(r"\((Objects?|Supports?|Neutral|No objection)\)", raw_text, re.I)

        # Try to find date pattern
        date_match = re.search(r"Comment submitted date:\s*(\w+ \d+ \w+ \d+)", raw_text)

        comment = {
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

        # Extract comment body text - everything after the date line
        if date_match:
            comment["text"] = raw_text[date_match.end():].strip()
        elif text_el:
            comment["text"] = text_el.get_text(strip=True)

        comments.append(comment)
    return comments


def _get_pagination_info(soup: BeautifulSoup) -> dict:
    """Extract pagination info from a page."""
    pager = soup.select_one(".pagerInfo, .pagination-info")
    total_pages = 1
    current_page = 1

    # Count page links
    page_links = soup.select("a[href*='Pager.page=']")
    page_numbers = set()
    for link in page_links:
        match = re.search(r"Pager\.page=(\d+)", link["href"])
        if match:
            page_numbers.add(int(match.group(1)))

    if page_numbers:
        total_pages = max(page_numbers)

    return {"total_pages": total_pages, "current_page": current_page}


@mcp.tool
def search_applications(
    query: str,
    status: str = "All",
) -> dict:
    """
    Search for planning applications on the New Forest District Council website.

    Args:
        query: Search term - can be a reference number (e.g. '25/10114'),
               postcode (e.g. 'BH24 3PG'), keyword, or single-line address.
        status: Filter by application status. One of: 'All', 'Current',
                'Decided', 'Withdrawn', 'Appeal'. Defaults to 'All'.

    Returns:
        A dict with:
        - results: list of matching applications with reference, address,
                   proposal, status and key_val (internal ID for further lookups)
        - total_count: number of results
        - message: any informational message from the site
    """
    client, csrf = _get_session_and_csrf()

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

    # Check for error/info messages
    message = ""
    error_box = soup.select_one(".errorMsg, .warningMsg, .errors li, .messages li")
    if error_box:
        message = error_box.get_text(strip=True)

    results = []

    # Check if we landed directly on a single application's details page
    # (happens when the search query matches exactly one application)
    summary_heading = soup.select_one("h1")
    if summary_heading and "Application Summary" in summary_heading.get_text():
        # Single result - parse directly
        ref_el = soup.select_one("h2") or soup.find(string=re.compile(r"\d{2}/\d+"))
        app_ref = ""
        if ref_el:
            app_ref = ref_el.get_text(strip=True) if hasattr(ref_el, "get_text") else str(ref_el).strip()

        # Get keyVal from a tab link
        key_val = None
        for a in soup.select("a[href*='keyVal=']"):
            key_val = _extract_key_val(a["href"])
            if key_val:
                break

        table_data = _parse_table(soup)
        results.append(
            {
                "reference": table_data.get("Reference", app_ref),
                "address": table_data.get("Address", ""),
                "proposal": table_data.get("Proposal", ""),
                "status": table_data.get("Status", ""),
                "key_val": key_val,
                "url": f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}" if key_val else str(resp.url),
            }
        )
        return {"results": results, "total_count": 1, "message": message}

    # Multiple results page
    result_items = soup.select("li.searchresult, .search-result, .applicationRow")

    if not result_items:
        # Try table rows
        result_items = soup.select("table.searchresults tbody tr, #searchresults tbody tr")

    for item in result_items:
        link = item.select_one("a[href*='applicationDetails']")
        if not link:
            continue

        key_val = _extract_key_val(link["href"])
        ref = link.get_text(strip=True)

        # Get address and description from surrounding text
        meta = item.select_one(".address, .metaData")
        address = meta.get_text(strip=True) if meta else ""

        desc = item.select_one(".description, .proposal")
        proposal = desc.get_text(strip=True) if desc else ""

        status_el = item.select_one(".status")
        app_status = status_el.get_text(strip=True) if status_el else ""

        results.append(
            {
                "reference": ref,
                "address": address,
                "proposal": proposal,
                "status": app_status,
                "key_val": key_val,
                "url": f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}",
            }
        )

    return {
        "results": results,
        "total_count": len(results),
        "message": message,
    }


@mcp.tool
def get_application_details(key_val: str) -> dict:
    """
    Get full details for a planning application.

    Args:
        key_val: The internal key value for the application (returned by
                 search_applications, e.g. '_NEWFO_DCAPR_223030').

    Returns:
        A dict with:
        - summary: core application fields (reference, address, proposal, status etc.)
        - further_information: applicant details, case officer, parish, ward etc.
        - important_dates: validated date, consultation dates, committee date etc.
        - progress: current stage in the application lifecycle
        - url: link to the public application page
    """
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=SSL_VERIFY)

    summary_data = {}
    further_data = {}
    dates_data = {}
    progress = ""

    # Fetch summary tab
    resp = client.get(f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    summary_data = _parse_table(soup)

    # Extract current progress step
    progress_steps = soup.select(".progressBar .step, .progress-bar .step, .progressBar li")
    active = soup.select_one(".progressBar .current, .progressBar .active, .progressBar strong")
    if active:
        progress = active.get_text(strip=True)

    # Fetch further information tab
    resp2 = client.get(f"{DETAILS_URL}?activeTab=details&keyVal={key_val}")
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, "lxml")
    further_data = _parse_table(soup2)

    # Fetch important dates tab
    resp3 = client.get(f"{DETAILS_URL}?activeTab=dates&keyVal={key_val}")
    resp3.raise_for_status()
    soup3 = BeautifulSoup(resp3.text, "lxml")
    dates_data = _parse_table(soup3)

    return {
        "summary": summary_data,
        "further_information": further_data,
        "important_dates": dates_data,
        "progress": progress,
        "url": f"{DETAILS_URL}?activeTab=summary&keyVal={key_val}",
    }


@mcp.tool
def get_public_comments(
    key_val: str,
    page: int = 1,
) -> dict:
    """
    Get public (neighbour) comments for a planning application.

    Args:
        key_val: The internal key value for the application (from search_applications).
        page: Page number to retrieve (default 1). Each page has up to 10 comments.

    Returns:
        A dict with:
        - comments: list of comment objects with name, stance, date and text fields
        - statistics: total consulted, comments received, objections, supporting counts
        - page: current page number
        - total_pages: total number of pages available
        - url: URL of this comments page
    """
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=SSL_VERIFY)

    url = f"{DETAILS_URL}?activeTab=neighbourComments&keyVal={key_val}"
    if page > 1:
        url += f"&neighbourCommentsPager.page={page}"

    resp = client.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Extract statistics
    stats = {}
    stats_area = soup.select_one(".commentStats, .statistics")
    if not stats_area:
        # Try to find the stats text inline
        stats_text = soup.get_text(" ")
        for pattern, key in [
            (r"Total Consulted:\s*([\d,]+)", "total_consulted"),
            (r"Comments Received:\s*([\d,]+)", "comments_received"),
            (r"Objections:\s*([\d,]+)", "objections"),
            (r"Supporting:\s*([\d,]+)", "supporting"),
        ]:
            match = re.search(pattern, stats_text)
            if match:
                stats[key] = match.group(1).replace(",", "")

    comments = _parse_comments(soup)
    pagination = _get_pagination_info(soup)

    return {
        "comments": comments,
        "statistics": stats,
        "page": page,
        "total_pages": pagination["total_pages"],
        "url": url,
    }


@mcp.tool
def get_consultee_comments(
    key_val: str,
    page: int = 1,
) -> dict:
    """
    Get consultee comments (statutory and technical consultees) for a planning application.

    These are comments from organisations like the Environment Agency, parish councils,
    highways authority etc., as opposed to members of the public.

    Args:
        key_val: The internal key value for the application (from search_applications).
        page: Page number to retrieve (default 1). Each page has up to 5 comments.

    Returns:
        A dict with:
        - comments: list of comment objects with name, consultation_date and text fields
        - page: current page number
        - total_pages: total number of pages available
        - url: URL of this comments page
    """
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=SSL_VERIFY)

    url = f"{DETAILS_URL}?activeTab=consulteeComments&keyVal={key_val}"
    if page > 1:
        url += f"&consulteeCommentsPager.page={page}"

    resp = client.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    comments = []
    for comment_div in soup.select(".comment"):
        # Consultee name is in h2
        name_el = comment_div.select_one("h2, .consultationName")
        consultee_name = name_el.get_text(strip=True) if name_el else ""

        # Each .commentText block is a separate consultation response
        comment_blocks = comment_div.select(".commentText")
        if comment_blocks:
            for block in comment_blocks:
                date_el = block.select_one("h3")
                consult_date = ""
                if date_el and "Consultation Date" in date_el.get_text():
                    # Date is the text after the h3 element, not inside it
                    date_el.extract()  # remove h3 to get remaining text
                    consult_date = block.get_text(" ", strip=True)
                else:
                    consult_date = block.get_text(" ", strip=True)

                comment_text = consult_date  # the remaining text IS the comment
                if "Comment can be viewed" in comment_text:
                    comment_text = "Comment can be viewed under Related Documents"

                comments.append(
                    {
                        "consultee": consultee_name,
                        "consultation_date": consult_date.replace("Comment can be viewed under Related Documents", "").strip(),
                        "text": comment_text,
                    }
                )
        else:
            raw_text = comment_div.get_text(" ", strip=True)
            comment_text = "Comment can be viewed under Related Documents" if "Comment can be viewed" in raw_text else raw_text
            comments.append(
                {
                    "consultee": consultee_name,
                    "consultation_date": "",
                    "text": comment_text,
                }
            )

    pagination = _get_pagination_info(soup)

    return {
        "comments": comments,
        "page": page,
        "total_pages": pagination["total_pages"],
        "url": url,
    }


PAGE_SIZE = 25  # Documents to return per page call


@mcp.tool
def get_documents(
    key_val: str,
    document_type: str = "Show All",
    page: int = 1,
    order_by: str = "date",
    order_direction: str = "descending",
) -> dict:
    """
    Get documents associated with a planning application.

    The site returns all documents in one HTML response; this tool paginates
    them client-side returning 25 per call.

    Args:
        key_val: The internal key value for the application (from search_applications).
        document_type: Filter by document type. Use 'Show All' for all documents,
                       or a specific type such as 'Plans', 'Consultee Comment',
                       'Applications Processing', 'Representees', 'Reports',
                       'Submitted Applications', 'Superseded Plans'.
        page: Page number to return (default 1, 25 documents per page).
        order_by: Sort field - one of 'date', 'documentType', 'drawingNumber',
                  'description'. Defaults to 'date'.
        order_direction: Sort direction - 'ascending' or 'descending'. Defaults to 'descending'.

    Returns:
        A dict with:
        - documents: list of up to 25 document objects, each with:
            - date: date published
            - type: document type
            - drawing_number: drawing reference (may be empty)
            - description: document description
            - download_url: direct URL to download/view the document
        - available_types: list of document type filter options
        - page: current page number
        - total_pages: total number of pages (at 25 per page)
        - total_count: total number of documents matching the filter
        - url: URL of the documents page
    """
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=60, verify=SSL_VERIFY)

    url = (
        f"{DETAILS_URL}?activeTab=documents&keyVal={key_val}"
        f"&documentOrdering.orderBy={order_by}"
        f"&documentOrdering.orderDirection={order_direction}"
    )

    # Fetch base URL first to get available document types (the ordered URL strips the dropdown options)
    base_url = f"{DETAILS_URL}?activeTab=documents&keyVal={key_val}"
    resp_base = client.get(base_url)
    resp_base.raise_for_status()
    soup_base = BeautifulSoup(resp_base.text, "lxml")

    available_types = []
    type_select = soup_base.select_one("select#documentType, select[name='documentType']")
    if type_select:
        for option in type_select.select("option"):
            label = option.get_text(strip=True)
            val = option.get("value", "")
            # Skip the "Show All" sentinel value (value="0")
            if label and val != "0":
                available_types.append(label)

    # Now fetch the ordered/sorted URL for the actual document list
    resp = client.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # The table has no tbody - rows are direct children of table
    table = soup.find("table")
    if not table:
        return {
            "documents": [],
            "available_types": available_types,
            "page": page,
            "total_pages": 1,
            "total_count": 0,
            "url": url,
        }

    all_rows = table.find_all("tr")
    # Table columns: [checkbox] [date] [type] [measure] [drawing_number] [description] [view]
    # Row 0 is the header row (th/td with labels)
    HEADER_TEXTS = {"Date Published", "Document Type", "Drawing Number", "Description", "Measure", "View"}

    all_documents = []
    for row in all_rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        # Get the download link from the last cell
        link = row.find("a", href=lambda h: h and "/files/" in h)
        download_url = ""
        if link:
            href = link["href"]
            download_url = (
                f"https://planning.newforest.gov.uk{href}"
                if href.startswith("/")
                else href
            )

        # Cells: 0=checkbox, 1=date, 2=type, 3=measure(img), 4=drawing_number, 5=description, 6=view
        date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        type_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        drawing_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
        desc_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""

        # Skip header rows
        if date_text in HEADER_TEXTS or not date_text:
            continue

        doc = {
            "date": date_text,
            "type": type_text,
            "drawing_number": drawing_text,
            "description": desc_text,
            "download_url": download_url,
        }

        # Apply document_type filter client-side if needed
        if document_type != "Show All" and type_text != document_type:
            continue

        all_documents.append(doc)

    total_count = len(all_documents)
    total_pages = max(1, math.ceil(total_count / PAGE_SIZE))

    # Paginate
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_docs = all_documents[start:end]

    return {
        "documents": page_docs,
        "available_types": available_types,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "url": url,
    }


if __name__ == "__main__":
    mcp.run()
