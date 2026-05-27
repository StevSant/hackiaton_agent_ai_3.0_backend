# Re-export the canonical User from the domain layer.
# Infrastructure code (ports, adapters, deps.py) that imported this path
# will continue to work without changes.
from app.domain.auth.user import User

__all__ = ["User"]
