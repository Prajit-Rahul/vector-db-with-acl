# src/vecgate/__init__.py
"""VecGate — ACL-controlled vector search for pgvector."""

__version__ = "0.1.0"

from vecgate.sdk import VecGate, AsyncVecGate

__all__ = ["VecGate", "AsyncVecGate", "__version__"]
