# src/vecgate/cli/commands/init_.py
import typer
from rich.console import Console

console = Console()


def init_cmd(
    db_url: str = typer.Option(..., "--db-url", envvar="VECGATE_DATABASE_URL",
                                help="PostgreSQL connection string (vecgate_admin role)"),
    enable_rls: bool = typer.Option(False, "--enable-rls",
                                     help="Enable PostgreSQL RLS backstop on chunks"),
):
    """Bootstrap VecGate schema. Idempotent — safe to run on existing DB."""
    import asyncio
    from vecgate import AsyncVecGate
    from vecgate.core.config import Settings

    async def _run():
        vg = AsyncVecGate(settings=Settings(database_url=db_url, admin_database_url=db_url))
        await vg.init(enable_rls=enable_rls)

    try:
        asyncio.run(_run())
        console.print("[green]✓[/green] Schema initialised")
        if enable_rls:
            console.print("[green]✓[/green] RLS enabled on chunks")
    except Exception as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)
