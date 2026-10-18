"""Reciprocal Rank Fusion (RRF) algorithm for hybrid search (FR-2)."""

from typing import Any, Dict, List, Tuple


def merge_rrf(
    porter_hits: List[Tuple[Any, ...]],
    trigram_hits: List[Tuple[Any, ...]],
    k: int = 60,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Merge ranked results from Porter and Trigram indexes using RRF (k=60)."""
    scores: Dict[Any, float] = {}
    data_map: Dict[Any, Tuple[Any, ...]] = {}

    # Rank Porter hits (already ordered by BM25 ascending)
    for rank, hit in enumerate(porter_hits, start=1):
        rowid = hit[0]
        data_map[rowid] = hit
        scores[rowid] = scores.get(rowid, 0.0) + (1.0 / (k + rank))

    # Rank Trigram hits
    for rank, hit in enumerate(trigram_hits, start=1):
        rowid = hit[0]
        if rowid not in data_map:
            data_map[rowid] = hit
        scores[rowid] = scores.get(rowid, 0.0) + (1.0 / (k + rank))

    # Sort descending by RRF score
    sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    results = []
    for rowid, score in sorted_items[:top_n]:
        hit = data_map[rowid]
        # (rowid, heading_path, snippet_text, source_id, namespace, agent_id, created_at, bm25_score)
        results.append({
            "chunk_id": str(hit[0]),
            "heading_path": hit[1] or "",
            "snippet": hit[2] or "",
            "source_id": hit[3],
            "namespace": hit[4],
            "agent_id": hit[5],
            "created_at": hit[6],
            "score": round(score, 6),
        })

    return results
