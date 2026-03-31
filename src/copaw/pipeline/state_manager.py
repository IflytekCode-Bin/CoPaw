# -*- coding: utf-8 -*-
"""State Manager for pipeline checkpoint and recovery.

Provides persistent storage for pipeline execution state, enabling:
- Checkpoint saving at each step
- Resume from failure
- Execution history queries
- Rollback support

Supports SQLite and JSON backends.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentscope.message import Msg

logger = logging.getLogger(__name__)


class StateManager:
    """Manage pipeline execution state with checkpoint/resume capability.

    Example::

        sm = StateManager(storage_type="sqlite")
        await sm.save_checkpoint(
            pipeline_id="pl_abc123",
            step=0,
            agent_id="analyst",
            input_msg=user_msg,
            output_msg=result_msg,
        )
        checkpoint = await sm.load_checkpoint("pl_abc123", step=0)
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        storage_type: str = "sqlite",
    ) -> None:
        """
        Args:
            storage_path: Directory for state files.  Defaults to
                ``~/.copaw/pipeline_states``.
            storage_type: ``"sqlite"`` or ``"json"``.
        """
        if storage_path is None:
            storage_path = Path.home() / ".copaw" / "pipeline_states"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.storage_type = storage_type

        if storage_type == "sqlite":
            self.db_path = self.storage_path / "pipeline_states.db"
            self._init_db()
        elif storage_type != "json":
            raise ValueError(
                f"Invalid storage_type '{storage_type}'. "
                "Must be 'sqlite' or 'json'.",
            )

    # ------------------------------------------------------------------
    # SQLite initialization
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_id TEXT NOT NULL,
                step INTEGER NOT NULL,
                agent_id TEXT NOT NULL,
                input_msg TEXT,
                output_msg TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
            """,
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_id
            ON pipeline_states(pipeline_id)
            """,
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_step
            ON pipeline_states(pipeline_id, step)
            """,
        )
        conn.commit()
        conn.close()
        logger.debug("StateManager: SQLite DB initialized at %s", self.db_path)

    # ------------------------------------------------------------------
    # Save checkpoint
    # ------------------------------------------------------------------

    async def save_checkpoint(
        self,
        pipeline_id: str,
        step: int,
        agent_id: str,
        input_msg: Msg | None = None,
        output_msg: Msg | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Save a checkpoint for a pipeline step.

        Args:
            pipeline_id: Unique pipeline execution ID.
            step: Step index (0-based).
            agent_id: Agent identifier.
            input_msg: Input message to the agent.
            output_msg: Output message from the agent.
            metadata: Additional metadata dict.
        """
        timestamp = datetime.now().isoformat()

        if self.storage_type == "sqlite":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_states
                (pipeline_id, step, agent_id, input_msg, output_msg,
                 timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pipeline_id,
                    step,
                    agent_id,
                    json.dumps(input_msg.to_dict()) if input_msg else None,
                    json.dumps(output_msg.to_dict()) if output_msg else None,
                    timestamp,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()
            conn.close()
        else:
            # JSON storage
            state_file = self.storage_path / f"{pipeline_id}.json"
            states = []
            if state_file.exists():
                with open(state_file, encoding="utf-8") as f:
                    states = json.load(f)

            states.append(
                {
                    "step": step,
                    "agent_id": agent_id,
                    "input_msg": input_msg.to_dict() if input_msg else None,
                    "output_msg": output_msg.to_dict() if output_msg else None,
                    "timestamp": timestamp,
                    "metadata": metadata,
                },
            )

            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(states, f, indent=2, ensure_ascii=False)

        logger.debug(
            "Saved checkpoint: pipeline=%s step=%d agent=%s",
            pipeline_id,
            step,
            agent_id,
        )

    # ------------------------------------------------------------------
    # Load checkpoint
    # ------------------------------------------------------------------

    async def load_checkpoint(
        self,
        pipeline_id: str,
        step: int | None = None,
    ) -> Dict[str, Any] | None:
        """Load a checkpoint for a pipeline.

        Args:
            pipeline_id: Pipeline execution ID.
            step: If provided, load the checkpoint for that step.
                Otherwise load the *latest* checkpoint.

        Returns:
            A dict with keys: id, pipeline_id, step, agent_id,
            input_msg, output_msg, timestamp, metadata.
            Returns ``None`` if no checkpoint is found.
        """
        if self.storage_type == "sqlite":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if step is not None:
                cursor.execute(
                    """
                    SELECT * FROM pipeline_states
                    WHERE pipeline_id = ? AND step = ?
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (pipeline_id, step),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM pipeline_states
                    WHERE pipeline_id = ?
                    ORDER BY step DESC, timestamp DESC LIMIT 1
                    """,
                    (pipeline_id,),
                )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return {
                "id": row[0],
                "pipeline_id": row[1],
                "step": row[2],
                "agent_id": row[3],
                "input_msg": json.loads(row[4]) if row[4] else None,
                "output_msg": json.loads(row[5]) if row[5] else None,
                "timestamp": row[6],
                "metadata": json.loads(row[7]) if row[7] else None,
            }
        else:
            # JSON storage
            state_file = self.storage_path / f"{pipeline_id}.json"
            if not state_file.exists():
                return None

            with open(state_file, encoding="utf-8") as f:
                states = json.load(f)

            if not states:
                return None

            if step is not None:
                for s in reversed(states):
                    if s["step"] == step:
                        return s
                return None
            else:
                return states[-1]

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_pipeline_history(
        self,
        pipeline_id: str,
    ) -> List[Dict[str, Any]]:
        """Retrieve all checkpoints for a pipeline in chronological order.

        Returns:
            A list of checkpoint dicts.
        """
        if self.storage_type == "sqlite":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM pipeline_states
                WHERE pipeline_id = ?
                ORDER BY step ASC, timestamp ASC
                """,
                (pipeline_id,),
            )
            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": row[0],
                    "pipeline_id": row[1],
                    "step": row[2],
                    "agent_id": row[3],
                    "input_msg": json.loads(row[4]) if row[4] else None,
                    "output_msg": json.loads(row[5]) if row[5] else None,
                    "timestamp": row[6],
                    "metadata": json.loads(row[7]) if row[7] else None,
                }
                for row in rows
            ]
        else:
            state_file = self.storage_path / f"{pipeline_id}.json"
            if not state_file.exists():
                return []

            with open(state_file, encoding="utf-8") as f:
                return json.load(f)

    async def list_pipelines(self) -> List[str]:
        """List all pipeline IDs that have saved state.

        Returns:
            A list of pipeline_id strings.
        """
        if self.storage_type == "sqlite":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT pipeline_id FROM pipeline_states",
            )
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        else:
            return [
                p.stem
                for p in self.storage_path.glob("*.json")
                if p.is_file()
            ]
