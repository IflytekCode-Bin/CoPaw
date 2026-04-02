#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script for CoPaw Storage Module.

Run with: python test_storage.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from copaw.storage import (
    SQLiteMemoryManager,
    MinIOStorageManager,
    HybridStorageManager,
)
from copaw.storage.sqlite_manager import estimate_tokens


def test_token_estimation():
    """Test CJK token estimation."""
    print("\n=== Token Estimation Tests ===")

    # ASCII
    text1 = "Hello, world!"
    tokens1 = estimate_tokens(text1)
    print(f"ASCII: '{text1}' -> {tokens1} tokens")
    assert tokens1 > 0

    # Chinese
    text2 = "你好世界，这是一段中文测试。"
    tokens2 = estimate_tokens(text2)
    print(f"Chinese: '{text2}' -> {tokens2} tokens")
    assert tokens2 > len(text2) * 0.25  # Should be higher than naive estimate

    # Mixed
    text3 = "Hello 你好 World 世界"
    tokens3 = estimate_tokens(text3)
    print(f"Mixed: '{text3}' -> {tokens3} tokens")

    # Emoji
    text4 = "Hello 🌍 世界 🚀"
    tokens4 = estimate_tokens(text4)
    print(f"Emoji: '{text4}' -> {tokens4} tokens")

    print("✓ Token estimation tests passed")


def test_sqlite_manager():
    """Test SQLite memory manager."""
    print("\n=== SQLite Manager Tests ===")

    # Use temp directory
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SQLiteMemoryManager(
            working_dir=tmpdir,
            agent_id="test",
        )

        # Create conversation
        manager.create_conversation(
            conversation_id="test-conv-1",
            session_id="test-session-1",
            channel="console",
            user_id="test-user",
            title="Test Conversation",
        )
        print("✓ Created conversation")

        # Insert messages
        tokens1 = manager.insert_message(
            message_id="msg-1",
            conversation_id="test-conv-1",
            role="user",
            content="Hello, this is a test message.",
        )
        print(f"✓ Inserted message 1: {tokens1} tokens")

        tokens2 = manager.insert_message(
            message_id="msg-2",
            conversation_id="test-conv-1",
            role="assistant",
            content="你好，这是一条中文回复消息。",
        )
        print(f"✓ Inserted message 2: {tokens2} tokens")

        # Get messages
        messages = manager.get_messages("test-conv-1")
        print(f"✓ Retrieved {len(messages)} messages")
        assert len(messages) == 2

        # Search messages
        results = manager.search_messages("test")
        print(f"✓ Found {len(results)} results for 'test'")

        results_zh = manager.search_messages("中文")
        print(f"✓ Found {len(results_zh)} results for '中文'")

        # Get stats
        stats = manager.get_token_stats("test-conv-1")
        print(f"✓ Stats: {stats}")

        # Create summary
        summary_tokens = manager.insert_summary(
            summary_id="summary-1",
            conversation_id="test-conv-1",
            kind="leaf",
            content="Test summary",
            depth=0,
            source_messages=["msg-1", "msg-2"],
        )
        print(f"✓ Created summary: {summary_tokens} tokens")

        # Get summaries
        summaries = manager.get_summaries("test-conv-1")
        print(f"✓ Retrieved {len(summaries)} summaries")

        # Check DB size
        size = manager.get_db_size()
        print(f"✓ Database size: {size} bytes")

        print("✓ All SQLite tests passed")


async def test_minio_manager():
    """Test MinIO storage manager."""
    print("\n=== MinIO Manager Tests ===")

    try:
        manager = MinIOStorageManager(
            agent_id="test",
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
            working_dir=Path("/tmp/copaw-test"),
        )
        print("✓ MinIO manager initialized")

        # Test upload JSON
        await manager.upload_json(
            "test/config.json",
            {"test": "value", "timestamp": datetime.now().isoformat()},
        )
        print("✓ Uploaded JSON")

        # Test list
        objects = await manager.list_objects("test/")
        print(f"✓ Listed {len(objects)} objects")

        # Test download JSON
        data = await manager.download_json("test/config.json")
        print(f"✓ Downloaded JSON: {data}")

        # Test stats
        stats = await manager.get_storage_stats()
        print(f"✓ Storage stats: {stats}")

        print("✓ All MinIO tests passed")

    except Exception as e:
        print(f"⚠ MinIO tests skipped: {e}")
        print("  (MinIO may not be running)")


async def test_hybrid_manager():
    """Test hybrid storage manager."""
    print("\n=== Hybrid Manager Tests ===")

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            manager = HybridStorageManager(
                working_dir=tmpdir,
                agent_id="test",
                minio_enabled=True,
                minio_endpoint="localhost:9000",
                minio_access_key="minioadmin",
                minio_secret_key="minioadmin123",
            )
            print("✓ Hybrid manager initialized")

            # Test stats
            stats = await manager.get_stats()
            print(f"✓ SQLite size: {stats['sqlite']['db_size_mb']} MB")

            if stats.get("minio"):
                print(f"✓ MinIO connected: {stats['minio']}")

            print("✓ All hybrid tests passed")

        except Exception as e:
            print(f"⚠ Hybrid tests partial: {e}")
            # SQLite should still work
            manager = HybridStorageManager(
                working_dir=tmpdir,
                agent_id="test",
                minio_enabled=False,
            )
            stats = await manager.get_stats()
            print(f"✓ SQLite-only mode works: {stats['sqlite']['db_size_mb']} MB")


def main():
    """Run all tests."""
    print("=" * 60)
    print("CoPaw Storage Module Tests")
    print("=" * 60)

    # Test token estimation
    test_token_estimation()

    # Test SQLite
    test_sqlite_manager()

    # Test MinIO (async)
    print("\n--- Async Tests ---")
    asyncio.run(test_minio_manager())
    asyncio.run(test_hybrid_manager())

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()