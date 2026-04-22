"""New Forest District Council Planning Applications MCP Server.

This is the entry point for the MCP server.  It creates the
:class:`fastmcp.FastMCP` instance, registers all tools from the
``nfdc.tools`` sub-package, and starts the server when run directly.

Tool implementations live in their own modules under ``nfdc/tools/``:

- :mod:`nfdc.tools.search`    — ``search_applications``
- :mod:`nfdc.tools.details`   — ``get_application_details``
- :mod:`nfdc.tools.comments`  — ``get_public_comments``, ``get_consultee_comments``
- :mod:`nfdc.tools.documents` — ``get_documents``

Shared HTTP utilities are in :mod:`nfdc.http`, HTML parsers in
:mod:`nfdc.parsers`, and constants (URLs, headers) in :mod:`nfdc.constants`.
"""

from fastmcp import FastMCP

from nfdc.tools import comments, details, documents, search

mcp = FastMCP(
    name="NFDC Planning",
    instructions=(
        "Tools for searching and retrieving planning application information "
        "from New Forest District Council. Use search_applications to find "
        "applications by reference number, keyword, postcode or address. "
        "Then use the other tools to get details, comments and documents."
    ),
)

search.register(mcp)
details.register(mcp)
comments.register(mcp)
documents.register(mcp)

if __name__ == "__main__":
    mcp.run()
