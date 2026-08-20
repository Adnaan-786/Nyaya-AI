from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant import TenantContext
from app.integrations.embeddings import embed_texts
from app.models.case import Case
from app.models.client import Client
from app.models.doc_chunk import DocChunk
from app.models.document import Document

RRF_K = 60  # standard reciprocal-rank-fusion constant


def _rrf_merge(*ranked_id_lists: list[UUID]) -> dict[UUID, float]:
    """
    Reciprocal Rank Fusion: combines several ranked ID lists (from
    different retrieval methods) into a single relevance score per ID,
    without needing the underlying scores to be on comparable scales.
    """
    scores: dict[UUID, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, item_id in enumerate(ranked_ids):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


async def search_cases(
    session: AsyncSession, tenant: TenantContext, q: str, limit: int
) -> list[dict]:
    stmt = (
        select(Case, func.similarity(Case.title, q).label("sim"))
        .where(Case.tenant_id == tenant.tenant_id)
        .where(
            (Case.title.op("%")(q))
            | Case.case_number.ilike(f"%{q}%")
            | Case.cnr.ilike(f"%{q}%")
        )
        .order_by(text("sim DESC"))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(case.id),
            "title": case.title,
            "case_number": case.case_number,
            "cnr": case.cnr,
            "highlight": case.title,
        }
        for case, _sim in rows
    ]


async def search_clients(
    session: AsyncSession, tenant: TenantContext, q: str, limit: int
) -> list[dict]:
    stmt = (
        select(Client, func.similarity(Client.name, q).label("sim"))
        .where(Client.tenant_id == tenant.tenant_id)
        .where((Client.name.op("%")(q)) | Client.phone.ilike(f"%{q}%"))
        .order_by(text("sim DESC"))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()

    return [
        {
            "id": str(client.id),
            "name": client.name,
            "phone": client.phone,
            "highlight": client.name,
        }
        for client, _sim in rows
    ]


async def search_documents(
    session: AsyncSession, tenant: TenantContext, q: str, limit: int
) -> list[dict]:
    """
    Hybrid retrieval per contract B.6: "Postgres FTS over ocr_text +
    case/client name trigram ... + vector similarity over chunks;
    merge with reciprocal-rank fusion".
    """

    # 1. Full-text search over ocr_text, with a headline as the highlight.
    tsquery = func.plainto_tsquery("english", q)
    fts_stmt = (
        select(
            Document.id,
            func.ts_headline("english", Document.extracted_text, tsquery).label(
                "highlight"
            ),
        )
        .where(Document.tenant_id == tenant.tenant_id)
        .where(Document.ocr_text.op("@@")(tsquery))
        .order_by(func.ts_rank(Document.ocr_text, tsquery).desc())
        .limit(limit * 2)
    )
    fts_rows = (await session.execute(fts_stmt)).all()
    fts_ids = [row[0] for row in fts_rows]
    fts_highlights = {row[0]: row[1] for row in fts_rows}

    # 2. Filename trigram match (catches queries that name the file itself).
    name_stmt = (
        select(Document.id)
        .where(Document.tenant_id == tenant.tenant_id)
        .where(Document.name.op("%")(q))
        .order_by(func.similarity(Document.name, q).desc())
        .limit(limit * 2)
    )
    name_ids = list((await session.execute(name_stmt)).scalars().all())

    # 3. Vector similarity over chunks (semantic match beyond exact keywords).
    vector_ids: list[UUID] = []
    try:
        [query_vector] = await embed_texts([q])
        vec_stmt = (
            select(DocChunk.document_id)
            .where(DocChunk.tenant_id == tenant.tenant_id)
            .order_by(DocChunk.embedding.cosine_distance(query_vector))
            .limit(limit * 2)
        )
        for doc_id in (await session.execute(vec_stmt)).scalars().all():
            if doc_id not in vector_ids:
                vector_ids.append(doc_id)
    except NotImplementedError:
        # Real embedding provider not configured; fall back to FTS+trigram only.
        pass

    merged_scores = _rrf_merge(fts_ids, name_ids, vector_ids)
    if not merged_scores:
        return []

    top_ids = sorted(merged_scores, key=lambda i: merged_scores[i], reverse=True)[:limit]

    result = await session.execute(select(Document).where(Document.id.in_(top_ids)))
    documents_by_id = {d.id: d for d in result.scalars().all()}

    output = []
    for doc_id in top_ids:
        document = documents_by_id.get(doc_id)
        if document is None:
            continue
        highlight = fts_highlights.get(doc_id) or (document.extracted_text or "")[:200]
        output.append(
            {
                "id": str(document.id),
                "name": document.name,
                "case_id": str(document.case_id) if document.case_id else None,
                "highlight": highlight,
            }
        )

    return output


async def universal_search(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    q: str,
    type_filter: str = "all",
    limit: int = 10,
) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {}

    if type_filter in ("all", "cases"):
        results["cases"] = await search_cases(session, tenant, q, limit)
    if type_filter in ("all", "clients"):
        results["clients"] = await search_clients(session, tenant, q, limit)
    if type_filter in ("all", "documents"):
        results["documents"] = await search_documents(session, tenant, q, limit)

    return results
