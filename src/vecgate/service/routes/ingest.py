# src/vecgate/service/routes/ingest.py
from fastapi import APIRouter, HTTPException, Request
from vecgate.core.errors import NotFoundError, ValidationError
from vecgate.core.models import IngestRequest, IngestResponse
from vecgate.ingest.ingest import ingest_chunks

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(body: IngestRequest, request: Request):
    conn = request.state.db
    settings = request.app.state.settings
    try:
        return await ingest_chunks(conn, body, settings.embedding_dimensions)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)
