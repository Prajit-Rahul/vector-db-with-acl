# src/vecgate/service/routes/admin.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from vecgate.admin.admin import AdminClient
from vecgate.core.errors import NotFoundError

router = APIRouter(prefix="/admin")


class FacetCreate(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(BaseModel):
    name: str
    facets: list[str] = []
    description: str | None = None


class AssignUser(BaseModel):
    user_id: int


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


def _admin(request: Request) -> AdminClient:
    return AdminClient(request.app.state.settings)


@router.get("/facets")
async def list_facets(request: Request):
    return await _admin(request).list_facets(request.state.db)


@router.post("/facets", status_code=201)
async def create_facet(body: FacetCreate, request: Request):
    fid = await _admin(request).create_facet(request.state.db, body.name, body.description)
    return {"id": fid, "name": body.name}


@router.get("/roles")
async def list_roles(request: Request):
    return await _admin(request).list_roles(request.state.db)


@router.post("/roles", status_code=201)
async def create_role(body: RoleCreate, request: Request):
    rid = await _admin(request).create_role(request.state.db, body.name,
                                             body.facets, body.description)
    return {"id": rid, "name": body.name}


@router.post("/roles/{role_id}/assign-user", status_code=200)
async def assign_role(role_id: int, body: AssignUser, request: Request):
    conn = request.state.db
    cur = await conn.execute("SELECT name FROM roles WHERE id = %s", (role_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Role not found")
    await _admin(request).assign_role(conn, body.user_id, row[0])
    return {"detail": "assigned"}


@router.get("/groups")
async def list_groups(request: Request):
    return await _admin(request).list_groups(request.state.db)


@router.post("/groups", status_code=201)
async def create_group(body: GroupCreate, request: Request):
    gid = await _admin(request).create_group(request.state.db, body.name, body.description)
    return {"id": gid, "name": body.name}


@router.post("/groups/{group_id}/assign-user", status_code=200)
async def assign_group(group_id: str, body: AssignUser, request: Request):
    conn = request.state.db
    cur = await conn.execute("SELECT name FROM groups WHERE id = %s::uuid", (group_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Group not found")
    await _admin(request).assign_group(conn, body.user_id, row[0])
    return {"detail": "assigned"}
