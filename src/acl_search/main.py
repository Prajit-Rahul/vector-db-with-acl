"""ASGI entrypoint: `uvicorn acl_search.main:app --reload`."""

from .api import create_app

app = create_app()
