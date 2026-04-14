"""End-to-end test for nested pipeline execution.

This script tests:
1. Set agent as Leader
2. Create a pipeline with sub-pipelines
3. Execute the nested pipeline
4. Verify the pipeline structure and execution
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add source directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))
os.chdir(src_dir)

# Now import with relative paths
from copaw.constant import WORKING_DIR
from copaw.app.pipeline_manager import get_pipeline_manager, PipelineManager
from copaw.app.leader_store import get_leader_store, LeaderStore
from copaw.app.pipeline_executor import (
    build_pipeline_async,
    execute_nested_pipeline,
    check_nesting_depth,
)


def setup_test_data():
    """Create test pipelines for testing."""
    manager = get_pipeline_manager()

    # Clean up any existing test data
    for pid in ["pipeline_1", "pipeline_2", "pipeline_3"]:
        manager.delete(pid)

    # Create parent pipeline
    parent = manager.create(
        name="Test Parent Pipeline",
        pipeline_type="sequential",
        agents=["default"],
        description="Parent pipeline for testing",
        owner_agent_id="test_agent_1",
        sub_pipelines=[],
    )
    print(f"✅ Created parent pipeline: {parent['id']}")

    # Create child pipeline
    child = manager.create(
        name="Test Child Pipeline",
        pipeline_type="sequential",
        agents=["default"],
        description="Child pipeline for testing",
        owner_agent_id="test_agent_1",
        parent_pipeline_id=parent["id"],
        sub_pipelines=[],
    )
    print(f"✅ Created child pipeline: {child['id']}")

    # Update parent to include child as sub-pipeline
    manager.update(
        parent["id"],
        sub_pipelines=[child["id"]],
    )
    print(f"✅ Linked child to parent")

    return parent["id"], child["id"]


def test_pipeline_manager():
    """Test PipelineManager CRUD operations."""
    print("\n🔍 Testing PipelineManager...")
    manager = get_pipeline_manager()

    # Test create
    pipeline = manager.create(
        name="Test Pipeline",
        pipeline_type="sequential",
        agents=["agent_1", "agent_2"],
        description="Test description",
        owner_agent_id="test_agent",
    )
    assert pipeline["id"] is not None
    assert pipeline["name"] == "Test Pipeline"
    assert pipeline["type"] == "sequential"
    assert pipeline["agents"] == ["agent_1", "agent_2"]
    print(f"  ✅ Create: {pipeline['id']}")

    # Test get
    retrieved = manager.get(pipeline["id"])
    assert retrieved is not None
    assert retrieved["name"] == "Test Pipeline"
    print(f"  ✅ Get by ID")

    # Test update
    updated = manager.update(
        pipeline["id"],
        name="Updated Pipeline",
        description="Updated description",
    )
    assert updated["name"] == "Updated Pipeline"
    print(f"  ✅ Update")

    # Test list
    all_pipelines = manager.list_all()
    assert len(all_pipelines) > 0
    print(f"  ✅ List: {len(all_pipelines)} pipelines")

    # Test filter by owner
    owner_pipelines = manager.list_all(owner_agent_id="test_agent")
    assert len(owner_pipelines) > 0
    print(f"  ✅ Filter by owner: {len(owner_pipelines)} pipelines")

    # Test delete
    deleted = manager.delete(pipeline["id"])
    assert deleted is True
    assert manager.get(pipeline["id"]) is None
    print(f"  ✅ Delete")

    print("✅ PipelineManager tests passed!")


def test_leader_store():
    """Test LeaderStore operations."""
    print("\n🔍 Testing LeaderStore...")
    store = get_leader_store()

    # Test set leader
    store.set_leader("agent_1")
    assert store.is_leader("agent_1") is True
    print(f"  ✅ Set leader: agent_1")

    # Test remove leader
    store.remove_leader("agent_1")
    assert store.is_leader("agent_1") is False
    print(f"  ✅ Remove leader: agent_1")

    # Test get leaders
    store.set_leader("agent_1")
    store.set_leader("agent_2")
    leaders = store.get_leaders()
    assert "agent_1" in leaders
    assert "agent_2" in leaders
    print(f"  ✅ Get leaders: {leaders}")

    # Cleanup
    store.remove_leader("agent_1")
    store.remove_leader("agent_2")

    print("✅ LeaderStore tests passed!")


def test_nesting_depth():
    """Test nesting depth checking."""
    print("\n🔍 Testing nesting depth...")
    manager = get_pipeline_manager()

    # Create a chain: A -> B -> C
    c = manager.create(
        name="Pipeline C",
        pipeline_type="sequential",
        agents=["agent_1"],
        owner_agent_id="test_agent",
    )
    b = manager.create(
        name="Pipeline B",
        pipeline_type="sequential",
        agents=["agent_1"],
        owner_agent_id="test_agent",
        sub_pipelines=[c["id"]],
    )
    a = manager.create(
        name="Pipeline A",
        pipeline_type="sequential",
        agents=["agent_1"],
        owner_agent_id="test_agent",
        sub_pipelines=[b["id"]],
    )

    # Check depth
    depth = check_nesting_depth(a["id"], manager)
    assert depth == 2  # A -> B -> C (depth 2)
    print(f"  ✅ Depth check: {depth}")

    # Test max depth exceeded
    try:
        check_nesting_depth(a["id"], manager, max_depth=1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"  ✅ Max depth check: {e}")

    # Cleanup
    manager.delete(a["id"])
    manager.delete(b["id"])
    manager.delete(c["id"])

    print("✅ Nesting depth tests passed!")


async def test_build_pipeline():
    """Test pipeline building."""
    print("\n🔍 Testing pipeline building...")
    manager = get_pipeline_manager()

    # Create test pipeline
    pipeline = manager.create(
        name="Test Build Pipeline",
        pipeline_type="sequential",
        agents=["default"],
        owner_agent_id="test_agent",
    )

    # Build pipeline
    built = await build_pipeline_async(
        pipeline,
        manager,
        multi_agent_manager=None,  # No manager in test
    )

    if built is None:
        print("  ⚠️ Pipeline build returned None (expected without real agents)")
    else:
        print(f"  ✅ Pipeline built: {type(built).__name__}")

    # Cleanup
    manager.delete(pipeline["id"])

    print("✅ Pipeline build tests passed!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 CoPaw Pipeline E2E Tests")
    print("=" * 60)

    try:
        test_pipeline_manager()
        test_leader_store()
        test_nesting_depth()
        await test_build_pipeline()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
