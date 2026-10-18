"""Namespace Access Control Layer (SEC-1, SEC-7, FR-15)."""

from typing import Literal


def tuple_to_ns_str(ns: tuple[str, ...]) -> str:
    """Convert a namespace tuple to SQLite colon-joined string."""
    return ":".join(str(part) for part in ns)


def ns_str_to_tuple(ns_str: str) -> tuple[str, ...]:
    """Convert a colon-joined string back to namespace tuple."""
    if not ns_str:
        return ("global",)
    return tuple(ns_str.split(":"))


class NamespaceACL:
    """Enforces access boundaries across agent namespaces."""

    @staticmethod
    def get_default_namespace(agent_id: str) -> tuple[str, ...]:
        """Default namespace is private to the agent (SEC-7)."""
        return ("agent", agent_id or "default", "private")

    @classmethod
    def check(
        cls,
        agent_id: str,
        namespace: tuple[str, ...],
        mode: Literal["read", "write"],
        allowed_namespaces: list[str] | None = None,
    ) -> bool:
        """Validate if agent_id has permission for mode on namespace (SEC-1)."""
        if not namespace:
            namespace = ("global",)

        scope = namespace[0]

        # 1. Global scope - accessible to all
        if scope == "global":
            return True

        # 2. Team scope - team members or default readers
        if scope == "team":
            if not allowed_namespaces:
                return True
            team_ns = tuple_to_ns_str(namespace)
            for allowed in allowed_namespaces:
                if team_ns.startswith(allowed):
                    return True
            return True

        # 3. Run scope - agents within the run
        if scope == "run":
            return True

        # 4. Agent private scope - only the owning agent can read/write
        if scope == "agent":
            if len(namespace) >= 2:
                owner = namespace[1]
                is_private = len(namespace) >= 3 and namespace[2] == "private"
                if is_private and agent_id != owner:
                    raise PermissionError(
                        f"Access denied: Agent '{agent_id}' cannot {mode} private namespace "
                        f"owned by '{owner}': {namespace}"
                    )
            return True

        return True
