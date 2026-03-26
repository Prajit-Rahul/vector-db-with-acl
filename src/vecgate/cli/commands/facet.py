# src/vecgate/cli/commands/facet.py
import typer
import asyncio
import psycopg
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage facets (dataset-level ACL)")
console = Console()
DB_OPT = typer.Option(..., "--db-url", envvar="VECGATE_DATABASE_URL")


@app.command("create")
def facet_create(name: str, db_url: str = DB_OPT,
                 description: str = typer.Option(None)):
    """Create a new facet."""
    from vecgate import AsyncVecGate

    async def _run():
        vg = AsyncVecGate(db_url=db_url)
        fid = await vg.create_facet(name, description)
        console.print(f"[green]✓[/green] Facet '{name}' created (id={fid})")
    asyncio.run(_run())


@app.command("list")
def facet_list(db_url: str = DB_OPT):
    """List all facets."""
    async def _run():
        async with await psycopg.AsyncConnection.connect(db_url) as conn:
            from vecgate.admin.admin import AdminClient
            from vecgate.core.config import Settings
            rows = await AdminClient(Settings(database_url=db_url)).list_facets(conn)
        t = Table("ID", "Name", "Description")
        for r in rows:
            t.add_row(str(r["id"]), r["name"], r["description"] or "")
        console.print(t)
    asyncio.run(_run())
