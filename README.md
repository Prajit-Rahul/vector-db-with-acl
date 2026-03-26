# VecGate

ACL-controlled vector search for pgvector. Two-layer RBAC in one SQL query.

## Install

```bash
pip install vecgate          # SDK
pip install vecgate[cli]     # + CLI
pip install vecgate[service] # + HTTP service
pip install vecgate[all]     # everything
```

## Quick Start

> **Note:** The SDK entry points (`VecGate`, `AsyncVecGate`) will be available once all tasks are complete. The snippet below shows the intended API.

```python
from vecgate import VecGate

vg = VecGate(db_url="postgresql://vecgate_app:pass@localhost/vecgate")
vg.init()
vg.create_facet("sales_data")
vg.create_role("sales_team", facets=["sales_data"])
vg.assign_role(user_id=1, role="sales_team")

results = vg.search(user_id=1, embedding=[...], top_k=10)
```

See the [full documentation](docs/) for SDK reference, CLI commands, and deployment guides.
