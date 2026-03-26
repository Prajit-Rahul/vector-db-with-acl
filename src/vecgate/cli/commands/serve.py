# src/vecgate/cli/commands/serve.py
import typer


def serve_cmd(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    db_url: str = typer.Option(..., "--db-url", envvar="VECGATE_DATABASE_URL"),
):
    """Start the VecGate HTTP service."""
    import uvicorn
    from vecgate.service.app import create_app
    from vecgate.core.config import Settings
    app = create_app(settings=Settings(database_url=db_url, enable_audit=True))
    uvicorn.run(app, host=host, port=port)
