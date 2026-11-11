"""Agent swarm communication via shared state bus."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Message passed between agents in the swarm."""
    from_agent: str
    to_agent: Optional[str]  # None = broadcast
    content: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = ""

    def __post_init__(self):
        if not self.message_id:
            import uuid
            self.message_id = uuid.uuid4().hex[:8]


class AgentSwarm:
    """Manages communication between agents via a shared state bus."""

    def __init__(self):
        self._shared_state: dict[str, Any] = {}
        self._message_bus: list[Message] = []
        self._agent_registry: dict[str, Any] = {}

    def register_agent(self, name: str, agent_instance: Any) -> None:
        """Register an agent with the swarm."""
        self._agent_registry[name] = agent_instance
        logger.info(f"Agent registered: {name}")

    async def broadcast(self, content: dict[str, Any], from_agent: str, metadata: Optional[dict] = None) -> list[str]:
        """Broadcast a message to all agents."""
        msg = Message(
            from_agent=from_agent,
            to_agent=None,
            content=content,
            metadata=metadata or {},
        )
        self._message_bus.append(msg)
        
        notified = []
        for name, agent in self._agent_registry.items():
            if hasattr(agent, 'on_message'):
                await agent.on_message(msg)
            notified.append(name)
        
        logger.debug(f"Broadcast from {from_agent}: {list(content.keys())[:5]}")
        return notified

    async def send(self, content: dict[str, Any], from_agent: str, to_agent: str) -> bool:
        """Send a direct message to a specific agent."""
        msg = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
        )
        self._message_bus.append(msg)
        
        if to_agent in self._agent_registry:
            target = self._agent_registry[to_agent]
            if hasattr(target, 'receive_message'):
                await target.receive_message(msg)
            return True
        logger.warning(f"Agent {to_agent} not found for message")
        return False

    def update_shared_state(self, key: str, value: Any) -> None:
        """Update shared state accessible by all agents."""
        self._shared_state[key] = value

    def get_shared_state(self, key: Optional[str] = None) -> dict | Any:
        """Get shared state. If key is provided, return that specific value."""
        if key:
            return self._shared_state.get(key)
        return dict(self._shared_state)

    def clear_state(self) -> None:
        """Clear all shared state."""
        self._shared_state.clear()
        self._message_bus.clear()
