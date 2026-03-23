"""FastAPI application for ACL-aware semantic search."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status

from ..auth.dependencies import AuthContext, get_auth_context
from ..core.config import Settings, get_settings
from ..core.db import close_pool, init_pool
from ..core.errors import AuthorizationError, NotFoundError, ValidationError
from ..core.schemas import (
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    UpdateChunkAclGroupsRequest,
    UpdateChunkAclGroupsResponse,
    UpdateUserGroupsRequest,
    UpdateUserGroupsResponse,
)
from ..embeddings.provider import EmbeddingProvider, StubEmbeddingProvider
from ..repository.search_repository import AclSearchRepository
from ..service.search_service import AclSearchService


def create_app(
    settings: Settings | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    embedding_provider = embedding_provider or StubEmbeddingProvider(
        dimensions=settings.embedding_dimensions
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = init_pool(settings)
        repository = AclSearchRepository(embedding_dimensions=settings.embedding_dimensions)
        app.state.service = AclSearchService(
            pool=pool,
            repository=repository,
            max_top_k=settings.max_top_k,
        )
        app.state.embedding_provider = embedding_provider
        yield
        close_pool()

    app = FastAPI(
        title="ACL Semantic Search",
        version="1.0.0",
        lifespan=lifespan,
    )

    def get_service(request: Request) -> AclSearchService:
        return request.app.state.service

    def get_embedding_provider(request: Request) -> EmbeddingProvider:
        return request.app.state.embedding_provider

    @app.post("/ingest", response_model=IngestResponse)
    def ingest(
        payload: IngestRequest,
        auth: AuthContext = Depends(get_auth_context),
        service: AclSearchService = Depends(get_service),
    ) -> IngestResponse:
        """Insert chunk + ACL grants within the authenticated tenant scope."""
        try:
            chunk_id, assigned_groups = service.ingestChunkWithAcl(
                tenantId=auth.tenant_id,
                documentId=payload.document_id,
                chunkIndex=payload.chunk_index,
                content=payload.content,
                embedding=payload.embedding,
                tokenCount=payload.token_count,
                metadata=payload.metadata,
                groupIds=payload.acl_group_ids,
            )
            return IngestResponse(chunk_id=chunk_id, assigned_group_ids=assigned_groups)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    @app.put("/users/{user_id}/groups", response_model=UpdateUserGroupsResponse)
    def replace_user_groups(
        user_id: UUID,
        payload: UpdateUserGroupsRequest,
        auth: AuthContext = Depends(get_auth_context),
        service: AclSearchService = Depends(get_service),
    ) -> UpdateUserGroupsResponse:
        """Replace a tenant user's effective group memberships."""
        try:
            assigned_groups = service.replaceUserGroups(
                tenantId=auth.tenant_id,
                userId=user_id,
                groupIds=payload.group_ids,
            )
            return UpdateUserGroupsResponse(
                user_id=user_id,
                tenant_id=auth.tenant_id,
                group_ids=assigned_groups,
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    @app.put("/chunks/{chunk_id}/acl-groups", response_model=UpdateChunkAclGroupsResponse)
    def replace_chunk_acl_groups(
        chunk_id: int,
        payload: UpdateChunkAclGroupsRequest,
        auth: AuthContext = Depends(get_auth_context),
        service: AclSearchService = Depends(get_service),
    ) -> UpdateChunkAclGroupsResponse:
        """Replace ACL groups for a chunk within the authenticated tenant."""
        try:
            assigned_groups = service.replaceChunkAclGroups(
                tenantId=auth.tenant_id,
                chunkId=chunk_id,
                groupIds=payload.group_ids,
            )
            return UpdateChunkAclGroupsResponse(
                chunk_id=chunk_id,
                tenant_id=auth.tenant_id,
                assigned_group_ids=assigned_groups,
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    @app.post("/search", response_model=SearchResponse)
    def search(
        payload: SearchRequest,
        auth: AuthContext = Depends(get_auth_context),
        service: AclSearchService = Depends(get_service),
        embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    ) -> SearchResponse:
        """Secure semantic search over tenant-scoped ACL-authorized chunks only."""
        try:
            # Never trust client user_id for auth scope.
            if payload.user_id is not None and payload.user_id != auth.user_id:
                raise AuthorizationError("user_id in payload does not match authenticated user")

            if payload.query_embedding is not None:
                query_embedding = payload.query_embedding
            else:
                assert payload.query_text is not None
                query_embedding = embedding_provider.embed_query_text(payload.query_text)

            results = service.searchAuthorizedChunks(
                userId=auth.user_id,
                tenantId=auth.tenant_id,
                queryEmbedding=query_embedding,
                topK=payload.top_k,
            )
            return SearchResponse(
                user_id=auth.user_id,
                tenant_id=auth.tenant_id,
                top_k=payload.top_k,
                results=results,
            )
        except AuthorizationError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    return app
