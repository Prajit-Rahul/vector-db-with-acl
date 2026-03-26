# src/vecgate/service/routes/search.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import psycopg
from vecgate.acl.resolver import resolve_user_context
from vecgate.core.errors import AuthorizationError, ValidationError
from vecgate.core.models import SearchResult
from vecgate.search.engine import fan_out_search

router = APIRouter()


class SearchRequest(BaseModel):
    user_id: int
    embedding: list[float]
    top_k: int = 10


class SearchResponse(BaseModel):
    results: list[SearchResult]


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, request: Request):
    conn: psycopg.AsyncConnection = request.state.db
    settings = request.app.state.settings
    top_k = min(body.top_k, settings.max_top_k)
    try:
        ctx = await resolve_user_context(conn, body.user_id)
        results = await fan_out_search(
            conn, ctx, body.embedding, top_k, settings.embedding_dimensions
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=e.message)
    return SearchResponse(results=results)
