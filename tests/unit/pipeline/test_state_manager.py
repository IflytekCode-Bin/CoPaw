# -*- coding: utf-8 -*-
"""Unit tests for state manager."""

import json
import tempfile
from pathlib import Path

import pytest
from copaw.pipeline.state_manager import StateManager
from agentscope.message import Msg


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temp directory for state storage."""
    return tmp_path / "pipeline_states"


# -------------------------------------------------------------------
# SQLite backend
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_save_and_load(tmp_storage):
    """Test save and load checkpoint with SQLite."""
    sm = StateManager(storage_path=tmp_storage, storage_type="sqlite")

    msg = Msg(name="user", content="hello", role="user")
    await sm.save_checkpoint(
        pipeline_id="pl_test1",
        step=0,
        agent_id="agent_a",
        input_msg=msg,
        metadata={"key": "value"},
    )

    result = await sm.load_checkpoint("pl_test1", step=0)
    assert result is not None
    assert result["pipeline_id"] == "pl_test1"
    assert result["step"] == 0
    assert result["agent_id"] == "agent_a"
    assert result["metadata"]["key"] == "value"


@pytest.mark.asyncio
async def test_sqlite_load_latest(tmp_storage):
    """Test loading the latest checkpoint."""
    sm = StateManager(storage_path=tmp_storage, storage_type="sqlite")

    for step in range(3):
        await sm.save_checkpoint(
            pipeline_id="pl_test2",
            step=step,
            agent_id=f"agent_{step}",
        )

    result = await sm.load_checkpoint("pl_test2")
    assert result is not None
    assert result["step"] == 2


@pytest.mark.asyncio
async def test_sqlite_history(tmp_storage):
    """Test get pipeline history."""
    sm = StateManager(storage_path=tmp_storage, storage_type="sqlite")

    for step in range(5):
        await sm.save_checkpoint(
            pipeline_id="pl_test3",
            step=step,
            agent_id=f"agent_{step}",
        )

    history = await sm.get_pipeline_history("pl_test3")
    assert len(history) == 5
    assert history[0]["step"] == 0
    assert history[4]["step"] == 4


@pytest.mark.asyncio
async def test_sqlite_list_pipelines(tmp_storage):
    """Test listing pipelines."""
    sm = StateManager(storage_path=tmp_storage, storage_type="sqlite")

    await sm.save_checkpoint("pl_a", 0, "agent_1")
    await sm.save_checkpoint("pl_b", 0, "agent_1")

    pipelines = await sm.list_pipelines()
    assert set(pipelines) == {"pl_a", "pl_b"}


@pytest.mark.asyncio
async def test_sqlite_not_found(tmp_storage):
    """Test load nonexistent checkpoint returns None."""
    sm = StateManager(storage_path=tmp_storage, storage_type="sqlite")
    result = await sm.load_checkpoint("nonexistent")
    assert result is None


# -------------------------------------------------------------------
# JSON backend
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_json_save_and_load(tmp_storage):
    """Test save and load checkpoint with JSON."""
    sm = StateManager(storage_path=tmp_storage, storage_type="json")

    msg = Msg(name="user", content="hello", role="user")
    await sm.save_checkpoint(
        pipeline_id="pl_json1",
        step=0,
        agent_id="agent_a",
        input_msg=msg,
        metadata={"key": "value"},
    )

    result = await sm.load_checkpoint("pl_json1", step=0)
    assert result is not None
    assert result["step"] == 0
    assert result["agent_id"] == "agent_a"


@pytest.mark.asyncio
async def test_json_load_latest(tmp_storage):
    """Test loading latest checkpoint from JSON."""
    sm = StateManager(storage_path=tmp_storage, storage_type="json")

    for step in range(3):
        await sm.save_checkpoint(
            pipeline_id="pl_json2",
            step=step,
            agent_id=f"agent_{step}",
        )

    result = await sm.load_checkpoint("pl_json2")
    assert result["step"] == 2


@pytest.mark.asyncio
async def test_json_history(tmp_storage):
    """Test JSON history."""
    sm = StateManager(storage_path=tmp_storage, storage_type="json")

    for step in range(4):
        await sm.save_checkpoint(
            pipeline_id="pl_json3",
            step=step,
            agent_id=f"agent_{step}",
        )

    history = await sm.get_pipeline_history("pl_json3")
    assert len(history) == 4


@pytest.mark.asyncio
async def test_json_list_pipelines(tmp_storage):
    """Test listing pipelines in JSON mode."""
    sm = StateManager(storage_path=tmp_storage, storage_type="json")

    await sm.save_checkpoint("pl_x", 0, "agent_1")
    await sm.save_checkpoint("pl_y", 0, "agent_1")

    pipelines = await sm.list_pipelines()
    assert set(pipelines) == {"pl_x", "pl_y"}


@pytest.mark.asyncio
async def test_json_not_found(tmp_storage):
    """Test load nonexistent JSON checkpoint."""
    sm = StateManager(storage_path=tmp_storage, storage_type="json")
    result = await sm.load_checkpoint("nonexistent")
    assert result is None


# -------------------------------------------------------------------
# Invalid backend
# -------------------------------------------------------------------

def test_invalid_storage_type(tmp_storage):
    """Test invalid storage type raises error."""
    with pytest.raises(ValueError, match="Invalid storage_type"):
        StateManager(storage_path=tmp_storage, storage_type="redis")
