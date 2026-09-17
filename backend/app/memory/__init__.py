"""Person memory: each person's own rest preference plus shared space rules.

Isolation rule: a person can only read or edit their own preference. Other people's
preferences never appear in shared listings or in another person's agent context.
In-memory only (resets with the demo).
"""

from app.memory.service import MemoryService, PersonContext

__all__ = ["MemoryService", "PersonContext"]
