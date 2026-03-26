# src/vecgate/cli/commands/status.py
import typer
from rich.console import Console
from rich.table import Table

console = Console()


def status_cmd(
    db_url: str = typer.Option(..., "--db-url", envvar="VECGATE_DATABASE_URL"),
):
    """Show DB connection status and row counts per table."""
    import asyncio
    import psycopg

    async def _run():
        async with await psycopg.AsyncConnection.connect(db_url) as conn:
            tables = ["users", "roles", "facets", "groups", "documents", "chunks",
                      "chunk_acl_groups", "audit_log"]
            counts = {}
            for t in tables:
                cur = await conn.execute(f"SELECT count(*) FROM {t}")
                row = await cur.fetchone()
                counts[t] = row[0]

            cur = await conn.execute(
                "SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto')"
            )
            exts = await cur.fetchall()
            ext_names = {r[0] for r in exts}

            cur = await conn.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename='chunks' "
                "AND indexname LIKE 'idx_chunks_embedding_facet_%'"
            )
            idx_rows = await cur.fetchall()
        return counts, ext_names, [r[0] for r in idx_rows]

    try:
        counts, exts, hnsw_indexes = asyncio.run(_run())
    except Exception as e:
        console.print(f"[red]✗ Connection failed:[/red] {e}")
        raise typer.Exit(code=1)

    console.print(f"[green]✓[/green] Database connected")
    ext_str = "  ".join(f"{e} ✓" for e in sorted(exts))
    console.print(f"Extensions: {ext_str}")

    t = Table("Table", "Rows")
    for table, count in counts.items():
        t.add_row(table, str(count))
    console.print(t)

    if hnsw_indexes:
        console.print(f"HNSW indexes: {', '.join(hnsw_indexes)}")
    else:
        console.print("[yellow]No HNSW indexes found — create facets to add them[/yellow]")
