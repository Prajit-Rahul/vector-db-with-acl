# src/vecgate/cli/commands/group.py
import typer
import asyncio
from rich.console import Console

app = typer.Typer(help="Manage groups and user-group assignments")
console = Console()
DB_OPT = typer.Option(..., "--db-url", envvar="VECGATE_DATABASE_URL")


@app.command("create")
def group_create(name: str, db_url: str = DB_OPT,
                 description: str = typer.Option(None)):
    """Create a new group."""
    from vecgate import AsyncVecGate

    async def _run():
        gid = await AsyncVecGate(db_url=db_url).create_group(name, description)
        console.print(f"[green]✓[/green] Group '{name}' created (id={gid})")
    asyncio.run(_run())


@app.command("assign")
def group_assign(
    user_id: int = typer.Option(..., "--user"),
    group: str = typer.Option(..., "--group"),
    db_url: str = DB_OPT,
):
    """Assign a group to a user."""
    from vecgate import AsyncVecGate

    async def _run():
        await AsyncVecGate(db_url=db_url).assign_group(user_id, group)
        console.print(f"[green]✓[/green] Group '{group}' assigned to user {user_id}")
    asyncio.run(_run())
