# vecgate/tests/test_core.py
from vecgate.core.errors import (
    VecGateError, ConfigError, SchemaError, AuthorizationError,
    ValidationError, NotFoundError, BackendError,
)
from vecgate.core.models import (
    SearchResult, ChunkIn, IngestRequest, IngestResponse, UserContext,
)
from vecgate.core.config import Settings
import pytest

def test_error_hierarchy():
    err = AuthorizationError("no facets")
    assert isinstance(err, VecGateError)
    assert err.code == "AUTHORIZATION_ERROR"
    assert "no facets" in str(err)

def test_search_result_fields():
    r = SearchResult(id=1, document_id="doc-uuid", chunk_index=0,
                     content="hello", metadata={}, distance=0.25)
    assert r.distance == 0.25

def test_chunk_in_defaults():
    c = ChunkIn(content="text", embedding=[0.1]*1536, chunk_index=0)
    assert c.acl_groups == []
    assert c.metadata == {}

def test_ingest_request_validation():
    req = IngestRequest(
        document_id="550e8400-e29b-41d4-a716-446655440000",
        facet="sales_data",
        chunks=[ChunkIn(content="x", embedding=[0.1]*1536, chunk_index=0)]
    )
    assert req.facet == "sales_data"

def test_user_context_never_none():
    ctx = UserContext(user_id=1, facet_ids=[], group_ids=[])
    assert ctx.facet_ids == []
    assert ctx.group_ids == []

def test_settings_defaults():
    s = Settings()
    assert s.embedding_dimensions == 1536
    assert s.max_top_k == 100
    assert s.enable_rls is False
