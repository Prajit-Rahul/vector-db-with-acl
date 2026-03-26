# src/vecgate/cli/main.py
import typer
from vecgate.cli.commands import init_, facet, role, group, status, serve

app = typer.Typer(
    name="vecgate",
    help="VecGate — ACL-controlled vector search for pgvector",
    no_args_is_help=True,
)

app.add_typer(facet.app, name="facet")
app.add_typer(role.app, name="role")
app.add_typer(group.app, name="group")
app.command("init")(init_.init_cmd)
app.command("status")(status.status_cmd)
app.command("serve")(serve.serve_cmd)

if __name__ == "__main__":
    app()
