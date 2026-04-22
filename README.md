# New Forest District Council Planning MCP Server

An MCP (Model Context Protocol) server that gives Claude the ability to search and retrieve planning application information from the [New Forest District Council planning portal](https://planning.newforest.gov.uk/online-applications/).

Ask Claude things like:
- *"Look up planning application 25/10114"*
- *"What are the public objections to application 25/10114?"*
- *"Show me the documents for this planning application"*
- *"Who is the case officer and what is the current status?"*

---

## Installation

### Quick install (Mac)

Open **Terminal** and run:

```bash
curl -LsSf https://raw.githubusercontent.com/MJPinfield/nfdc-mcp-server/main/install.sh | bash
```

Then **quit and reopen Claude Desktop**. That's it.

---

### Manual install

Requires [uv](https://docs.astral.sh/uv/) and [Claude Desktop](https://claude.ai/download).

**1. Clone the repo**

```bash
git clone https://github.com/MJPinfield/nfdc-mcp-server.git
cd nfdc-mcp-server
```

**2. Install dependencies**

```bash
uv sync
```

**3. Add to Claude Desktop config**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "NFDC Planning": {
      "command": "/Users/YOUR_USERNAME/.local/bin/uv",
      "args": [
        "run",
        "--project",
        "/path/to/nfdc-mcp-server",
        "python",
        "/path/to/nfdc-mcp-server/main.py"
      ],
      "env": {}
    }
  }
}
```

Replace `/path/to/nfdc-mcp-server` with the actual path where you cloned the repo.

**4. Restart Claude Desktop**

---

## Tools

### `search_applications`

Search for planning applications by reference number, postcode, keyword or address.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Reference number (e.g. `25/10114`), postcode, keyword or address |
| `status` | string | `All` | Filter by status: `All`, `Current`, `Decided`, `Withdrawn`, `Appeal` |

Returns a list of matching applications, each with a `key_val` identifier used by all other tools.

---

### `get_application_details`

Get the full details of a planning application.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_val` | string | Internal ID returned by `search_applications` |

Returns:
- **Summary** — reference, address, proposal, status
- **Further information** — application type, case officer, parish, ward, applicant details
- **Important dates** — validated date, consultation period, committee date

---

### `get_public_comments`

Retrieve public (neighbour) comments on an application, paginated.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_val` | string | required | Internal ID from `search_applications` |
| `page` | integer | `1` | Page number (10 comments per page) |

Returns comments with name, stance (Objects / Supports), date and full comment text, plus headline statistics (total consulted, objections, supporting).

---

### `get_consultee_comments`

Retrieve statutory consultee responses (Environment Agency, Natural England, HCC Highways, parish councils etc.).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_val` | string | required | Internal ID from `search_applications` |
| `page` | integer | `1` | Page number (5 consultees per page) |

---

### `get_documents`

List all documents associated with an application, with direct download URLs.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_val` | string | required | Internal ID from `search_applications` |
| `document_type` | string | `Show All` | Filter by type: `Plans`, `Consultee Comment`, `Applications Processing`, `Reports`, `Representees`, `Submitted Applications`, `Superseded Plans` |
| `page` | integer | `1` | Page number (25 documents per page) |
| `order_by` | string | `date` | Sort by: `date`, `documentType`, `drawingNumber`, `description` |
| `order_direction` | string | `descending` | `ascending` or `descending` |

---

## Example conversation

```
You:     Look up planning application 25/10114

Claude:  This is a full planning application for the demolition of existing
         outbuildings and the erection of 140 dwellings at Snails Lane,
         Blashford. It was received on 6 Feb 2025 and is currently at the
         Recommendation and/or Committee stage.

         Case Officer: Robert Thain
         Parish: Ellingham Harbridge & Ibsley
         Ward: Ringwood North & Ellingham

You:     What's the public response been like?

Claude:  There are 971 public comments. 966 objections and only 3 in support.
         The main concerns raised are flooding (the site is a wet meadow that
         floods regularly), impact on the A338, pressure on local schools and
         GP surgeries, and harm to biodiversity at the adjacent Blashford
         Lakes SSSI...
```

---

## Notes

- **SSL**: The NFDC planning portal has a misconfigured TLS certificate chain. SSL verification is disabled to work around this server-side issue — the site is a known public government portal.
- **Rate limiting**: The server makes sequential HTTP requests with no artificial throttling. Be considerate with bulk queries.
- **Data**: All data is sourced directly from the live NFDC planning portal and reflects its current state.
