"""MCP tool modules for the NFDC planning server.

Each module in this package defines a ``register(mcp)`` function that
attaches one or more tools to a :class:`fastmcp.FastMCP` instance.

Modules:

- :mod:`nfdc.tools.search`    — ``search_applications``
- :mod:`nfdc.tools.details`   — ``get_application_details``
- :mod:`nfdc.tools.comments`  — ``get_public_comments``, ``get_consultee_comments``
- :mod:`nfdc.tools.documents` — ``get_documents``
"""
