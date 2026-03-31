# -*- coding: utf-8 -*-
"""Enhanced MsgHub for CoPaw multi-agent communication.

Extends AgentScope's MsgHub with:
- Message filtering (per-agent)
- Priority queue for ordered delivery
- Selective broadcast (exclude / include lists)
- Message history tracking
"""

import logging
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Sequence

from agentscope.agent import AgentBase
from agentscope.message import Msg
from agentscope.pipeline import MsgHub as _AgentScopeMsgHub

logger = logging.getLogger(__name__)

# Type alias for filter function: (msg, target_agent) -> bool
MessageFilterFn = Callable[[Msg, AgentBase], bool]

# Type alias for priority function: (msg) -> int  (higher = delivered first)
PriorityFn = Callable[[Msg], int]


class CoPawMsgHub(_AgentScopeMsgHub):
    """Enhanced message hub with filtering, priority, and history.

    CoPawMsgHub wraps AgentScope's ``MsgHub`` and adds features useful
    for CoPaw's multi-agent pipelines:

    - **Message filter**: A callable ``(msg, agent) -> bool`` that
      decides whether *agent* should receive *msg*.
    - **Priority queue**: An optional priority function that determines
      delivery order when messages are queued.
    - **Message history**: An optional bounded deque that records all
      messages broadcast through the hub.

    Basic usage is identical to AgentScope's MsgHub::

        async with CoPawMsgHub(
            participants=[alice, bob, charlie],
            announcement=Msg("system", "Welcome!", "system"),
        ) as hub:
            await alice()
            await bob()

    With filtering::

        def only_code_msgs(msg, agent):
            return "```" in str(msg.content)

        async with CoPawMsgHub(
            participants=[alice, bob],
            message_filter=only_code_msgs,
        ) as hub:
            await alice()  # only messages containing code reach bob
    """

    def __init__(
        self,
        participants: Sequence[AgentBase],
        announcement: Msg | List[Msg] | None = None,
        enable_auto_broadcast: bool = True,
        name: str | None = None,
        *,
        message_filter: MessageFilterFn | None = None,
        priority_fn: PriorityFn | None = None,
        history_maxlen: int | None = 200,
    ) -> None:
        """
        Args:
            participants: Agents in the hub.
            announcement: Initial message(s) broadcast on entry.
            enable_auto_broadcast: Auto-broadcast replies to all others.
            name: Hub name (random if not given).
            message_filter: Optional per-agent filter.
            priority_fn: Optional function to assign delivery priority.
            history_maxlen: Max messages kept in history (None = no limit).
        """
        super().__init__(
            participants=participants,
            announcement=announcement,
            enable_auto_broadcast=enable_auto_broadcast,
            name=name,
        )
        self.message_filter = message_filter
        self.priority_fn = priority_fn

        self._history: deque[Msg] = deque(maxlen=history_maxlen)
        self._pending_queue: List[tuple[int, Msg]] = []  # (priority, msg)

    # ------------------------------------------------------------------
    # Broadcast with filtering
    # ------------------------------------------------------------------

    async def broadcast(
        self,
        msg: Msg | List[Msg],
        exclude: Sequence[AgentBase] | None = None,
        include_only: Sequence[AgentBase] | None = None,
    ) -> None:
        """Broadcast a message to participants with optional filtering.

        Args:
            msg: Message(s) to broadcast.
            exclude: Agents that should *not* receive the message.
            include_only: If provided, *only* these agents receive it.
                Takes precedence over ``exclude``.
        """
        msgs = [msg] if isinstance(msg, Msg) else msg
        exclude_set = set(exclude) if exclude else set()

        for m in msgs:
            self._history.append(m)

            for agent in self.participants:
                # include_only filter
                if include_only is not None and agent not in include_only:
                    continue
                # exclude filter
                if agent in exclude_set:
                    continue
                # Custom message filter
                if self.message_filter and not self.message_filter(m, agent):
                    logger.debug(
                        "MsgHub '%s': filtered msg from agent '%s'",
                        self.name,
                        getattr(agent, "name", "?"),
                    )
                    continue

                await agent.observe(m)

    # ------------------------------------------------------------------
    # Priority queue
    # ------------------------------------------------------------------

    def enqueue(self, msg: Msg) -> None:
        """Add a message to the priority queue (not broadcast yet).

        Call :meth:`flush_queue` to broadcast all queued messages in
        priority order.
        """
        priority = self.priority_fn(msg) if self.priority_fn else 0
        self._pending_queue.append((priority, msg))

    async def flush_queue(
        self,
        exclude: Sequence[AgentBase] | None = None,
    ) -> int:
        """Broadcast all queued messages in priority order (high first).

        Returns:
            Number of messages broadcast.
        """
        if not self._pending_queue:
            return 0

        # Sort descending by priority
        self._pending_queue.sort(key=lambda x: x[0], reverse=True)
        count = len(self._pending_queue)

        for _priority, msg in self._pending_queue:
            await self.broadcast(msg, exclude=exclude)

        self._pending_queue.clear()
        return count

    # ------------------------------------------------------------------
    # History access
    # ------------------------------------------------------------------

    @property
    def history(self) -> List[Msg]:
        """Return the message history as a plain list."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear the message history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Dynamic membership
    # ------------------------------------------------------------------

    def add_participant(self, agent: AgentBase) -> None:
        """Add an agent to the hub at runtime."""
        if agent not in self.participants:
            self.participants.append(agent)
            # Re-wire auto-broadcast subscriptions
            if self.enable_auto_broadcast:
                self._reset_subscriber()
            logger.debug(
                "MsgHub '%s': added participant '%s'",
                self.name,
                getattr(agent, "name", "?"),
            )

    def remove_participant(self, agent: AgentBase) -> bool:
        """Remove an agent from the hub.

        Returns:
            True if the agent was found and removed.
        """
        try:
            self.participants.remove(agent)
            if self.enable_auto_broadcast:
                agent.remove_subscribers(self.name)
                self._reset_subscriber()
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        names = [getattr(a, "name", "?") for a in self.participants]
        return (
            f"<CoPawMsgHub name={self.name!r} "
            f"participants={names} "
            f"history_len={len(self._history)}>"
        )
