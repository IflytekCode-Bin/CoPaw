# -*- coding: utf-8 -*-
"""SQLite Memory Manager for CoPaw.

Provides local fast storage with:
- FTS5 full-text search
- DAG-based conversation summaries
- Token counting with CJK support
"""

import asyncio
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import SQLITE_SCHEMA

logger = logging.getLogger(__name__)


# ============================================================
# CJK Token Estimation (from lossless-claw-enhanced)
# ============================================================

CJK_CHAR_RE = re.compile(
    r'[\u2E80-\u9FFF\u3400-\u4DBF\uF900-\uFAFF'
    r'\uAC00-\uD7AF\u3040-\u309F\u30A0-\u30FF'
    r'\uFF00-\uFFEF\u3000-\u303F]'
)
SURROGATE_PAIR_RE = re.compile(r'[\uD800-\uDBFF][\uDC00-\uDFFF]')

CJK_TOKENS_PER_CHAR = 1.5
SUPPLEMENTARY_TOKENS_PER_CHAR = 2
ASCII_TOKENS_PER_CHAR = 0.25


def estimate_tokens(text: str) -> int:
    """Estimate token count with CJK awareness.

    This is much more accurate for Chinese/Japanese/Korean text
    compared to simple len(text) / 4.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Count supplementary-plane chars (emoji, etc.)
    supplementary_matches = SURROGATE_PAIR_RE.findall(text)
    supplementary_count = len(supplementary_matches)

    # Count CJK characters
    cjk_matches = CJK_CHAR_RE.findall(text)
    cjk_count = len(cjk_matches)

    if cjk_count == 0 and supplementary_count == 0:
        # Pure ASCII/Latin
        return int(len(text) * ASCII_TOKENS_PER_CHAR) + 1

    # Supplementary chars consume 2 code units each
    supplementary_code_units = supplementary_count * 2
    non_special_count = len(text) - cjk_count - supplementary_code_units

    tokens = (
        cjk_count * CJK_TOKENS_PER_CHAR
        + supplementary_count * SUPPLEMENTARY_TOKENS_PER_CHAR
        + non_special_count * ASCII_TOKENS_PER_CHAR
    )

    return int(tokens) + 1


class SQLiteMemoryManager:
    """SQLite-based memory manager for fast local queries.

    Features:
    - Conversation storage with FTS5 search
    - DAG-based summary compaction
    - Token counting with CJK support
    - Efficient range queries
    """

    def __init__(
        self,
        working_dir: str,
        agent_id: str = "default",
        db_name: str = "memory.db",
    ):
        """Initialize SQLite memory manager.

        Args:
            working_dir: Working directory for database
            agent_id: Agent identifier
            db_name: Database filename
        """
        self.working_dir = Path(working_dir)
        self.agent_id = agent_id
        self.db_path = self.working_dir / db_name

        self.working_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

        logger.info(f"SQLiteMemoryManager initialized: {self.db_path}")

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SQLITE_SCHEMA)
        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ============================================================
    # Conversation Methods
    # ============================================================

    def create_conversation(
        self,
        conversation_id: str,
        session_id: str,
        channel: str = "console",
        user_id: str = "default",
        title: Optional[str] = None,
    ) -> None:
        """Create a new conversation.

        Args:
            conversation_id: Unique conversation ID
            session_id: Session ID
            channel: Communication channel
            user_id: User ID
            title: Optional title
        """
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO conversations
            (conversation_id, session_id, channel, user_id, title)
            VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, session_id, channel, user_id, title))
        conn.commit()
        conn.close()

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?",
            (conversation_id,)
        ).fetchone()
        conn.close()

        return dict(row) if row else None

    def list_conversations(
        self,
        user_id: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List conversations with optional filters."""
        conn = self._get_conn()

        query = "SELECT * FROM conversations WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if channel:
            query += " AND channel = ?"
            params.append(channel)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ============================================================
    # Message Methods
    # ============================================================

    def insert_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        seq: Optional[int] = None,
    ) -> int:
        """Insert a message.

        Args:
            message_id: Unique message ID
            conversation_id: Conversation ID
            role: Message role (user/assistant/system/tool)
            content: Message content
            seq: Optional sequence number

        Returns:
            Token count
        """
        token_count = estimate_tokens(content)

        conn = self._get_conn()

        # Auto-calculate seq if not provided
        if seq is None:
            row = conn.execute(
                "SELECT MAX(seq) FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            ).fetchone()
            seq = (row[0] or -1) + 1

        conn.execute("""
            INSERT INTO messages
            (message_id, conversation_id, seq, role, content, token_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (message_id, conversation_id, seq, role, content, token_count))

        # Update FTS index
        conn.execute("""
            INSERT INTO messages_fts (rowid, content)
            VALUES (
                (SELECT rowid FROM messages WHERE message_id = ?),
                ?
            )
        """, (message_id, content))

        # Update conversation stats
        conn.execute("""
            UPDATE conversations
            SET message_count = message_count + 1,
                total_tokens = total_tokens + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE conversation_id = ?
        """, (token_count, conversation_id))

        conn.commit()
        conn.close()

        return token_count

    def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get messages for a conversation."""
        conn = self._get_conn()

        query = """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY seq ASC
        """
        params = [conversation_id]

        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_recent_messages(
        self,
        conversation_id: str,
        count: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get most recent messages."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY seq DESC
            LIMIT ?
        """, (conversation_id, count)).fetchall()
        conn.close()

        return list(reversed([dict(row) for row in rows]))

    # ============================================================
    # Search Methods
    # ============================================================

    def search_messages(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Full-text search messages.

        Args:
            query: Search query
            conversation_id: Optional conversation filter
            limit: Max results

        Returns:
            List of matching messages
        """
        conn = self._get_conn()

        if conversation_id:
            rows = conn.execute("""
                SELECT m.*, fts.rank
                FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?
                AND m.conversation_id = ?
                ORDER BY fts.rank
                LIMIT ?
            """, (query, conversation_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT m.*, fts.rank
                FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?
                ORDER BY fts.rank
                LIMIT ?
            """, (query, limit)).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def search_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search messages by time range."""
        conn = self._get_conn()

        if conversation_id:
            rows = conn.execute("""
                SELECT * FROM messages
                WHERE conversation_id = ?
                AND created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
            """, (conversation_id, start_time, end_time)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM messages
                WHERE created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
            """, (start_time, end_time)).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    # ============================================================
    # Summary Methods (DAG)
    # ============================================================

    def insert_summary(
        self,
        summary_id: str,
        conversation_id: str,
        kind: str,
        content: str,
        depth: int = 0,
        source_messages: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> int:
        """Insert a summary node.

        Args:
            summary_id: Unique summary ID
            conversation_id: Conversation ID
            kind: 'leaf' or 'condensed'
            content: Summary content
            depth: DAG depth (0 = leaf)
            source_messages: List of source message IDs
            model: Model used for summarization

        Returns:
            Token count
        """
        token_count = estimate_tokens(content)
        source_token_count = 0
        earliest_at = None
        latest_at = None

        # Calculate source stats if source messages provided
        if source_messages:
            conn = self._get_conn()
            placeholders = ','.join('?' * len(source_messages))
            rows = conn.execute(f"""
                SELECT token_count, created_at FROM messages
                WHERE message_id IN ({placeholders})
                ORDER BY created_at
            """, source_messages).fetchall()

            if rows:
                source_token_count = sum(r['token_count'] for r in rows)
                earliest_at = rows[0]['created_at']
                latest_at = rows[-1]['created_at']

            conn.close()

        # Insert summary
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO summaries
            (summary_id, conversation_id, kind, depth, content, token_count,
             source_token_count, model, earliest_at, latest_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (summary_id, conversation_id, kind, depth, content, token_count,
              source_token_count, model, earliest_at, latest_at))

        # Create edges to source messages
        if source_messages:
            for msg_id in source_messages:
                conn.execute("""
                    INSERT INTO summary_edges (parent_id, child_id)
                    VALUES (?, ?)
                """, (summary_id, msg_id))

        conn.commit()
        conn.close()

        return token_count

    def get_summaries(
        self,
        conversation_id: str,
        depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get summaries for a conversation."""
        conn = self._get_conn()

        if depth is not None:
            rows = conn.execute("""
                SELECT * FROM summaries
                WHERE conversation_id = ? AND depth = ?
                ORDER BY created_at ASC
            """, (conversation_id, depth)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM summaries
                WHERE conversation_id = ?
                ORDER BY depth, created_at ASC
            """, (conversation_id,)).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def get_summary_children(
        self,
        summary_id: str,
    ) -> List[str]:
        """Get child IDs for a summary."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT child_id FROM summary_edges
            WHERE parent_id = ?
        """, (summary_id,)).fetchall()
        conn.close()
        return [row['child_id'] for row in rows]

    # ============================================================
    # Statistics Methods
    # ============================================================

    def get_token_stats(
        self,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """Get token statistics."""
        conn = self._get_conn()

        if conversation_id:
            row = conn.execute("""
                SELECT
                    COUNT(*) as message_count,
                    SUM(token_count) as total_tokens,
                    AVG(token_count) as avg_tokens
                FROM messages
                WHERE conversation_id = ?
            """, (conversation_id,)).fetchone()
        else:
            row = conn.execute("""
                SELECT
                    COUNT(*) as message_count,
                    SUM(token_count) as total_tokens,
                    AVG(token_count) as avg_tokens
                FROM messages
            """).fetchone()

        conn.close()

        return {
            "message_count": row['message_count'] or 0,
            "total_tokens": row['total_tokens'] or 0,
            "avg_tokens": int(row['avg_tokens'] or 0),
        }

    def get_db_size(self) -> int:
        """Get database file size in bytes."""
        return self.db_path.stat().st_size if self.db_path.exists() else 0

    def vacuum(self) -> None:
        """Vacuum database to reclaim space."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("VACUUM")
        conn.close()
        logger.info("Database vacuumed")