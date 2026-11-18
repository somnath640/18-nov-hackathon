from mcp.server.fastmcp import FastMCP

from app.core.rag import HybridRAG

mcp = FastMCP("hybrid-rag")
rag = HybridRAG()


@mcp.tool()
def hybrid_retrieve(tenant_id: str, query: str, limit: int = 4) -> list[dict]:
    """Retrieve tenant-scoped chunks using BM25 and return citations."""
    hits = rag.retrieve(tenant_id, query, min(max(limit, 1), 50))
    return [{"chunk_id": chunk.chunk_id, "text": chunk.text, "score": score} for chunk, score in hits]


if __name__ == "__main__":
    mcp.run(transport="stdio")
