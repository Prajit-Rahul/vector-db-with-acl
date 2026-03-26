# src/vecgate/cli/commands/role.py
import typer
import asyncio
from rich.console import Console

app = typer.Typer(help="Manage roles and user-role assignments")
console = Console()
DB_OPT = typer.Option(..., "--db-url", envvar="VECGATE_DATABASE_URL")


@app.command("create")
def role_create(
    name: str,
    facets: str = typer.Option("", "--facets", help="Comma-separated facet names"),
    db_url: str = DB_OPT,
):
    """Create a new role."""
    from vecgate import AsyncVecGate
    facet_list = [f.strip() for f in facets.split(",") if f.strip()]

    async def _run():
        rid = await AsyncVecGate(db_url=db_url).create_role(name, facets=facet_list)
        console.print(f"[green]✓[/green] Role '{name}' created (id={rid})")
    asyncio.run(_run())


@app.command("assign")
def role_assign(
    user_id: int = typer.Option(..., "--user"),
    role: str = typer.Option(..., "--role"),
    db_url: str = DB_OPT,
):
    """Assign a role to a user."""
    from vecgate import AsyncVecGate

    async def _run():
        await AsyncVecGate(db_url=db_url).assign_role(user_id, role)
        console.print(f"[green]✓[/green] Role '{role}' assigned to user {user_id}")
    asyncio.run(_run())
