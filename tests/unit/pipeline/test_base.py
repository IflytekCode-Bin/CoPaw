# -*- coding: utf-8 -*-
"""Unit tests for pipeline base class."""

import pytest
from copaw.pipeline.base import PipelineBase, PipelineStatus


class MockPipeline(PipelineBase):
    """Mock pipeline for testing."""

    async def execute(self, msg=None, **kwargs):
        return msg


@pytest.mark.asyncio
async def test_pipeline_creation():
    """Test pipeline creation."""
    pipeline = MockPipeline(name="test", agents=[])
    assert pipeline.name == "test"
    assert pipeline.status == PipelineStatus.PENDING
    assert len(pipeline.agents) == 0
    assert pipeline.pipeline_id.startswith("pl_")


@pytest.mark.asyncio
async def test_pipeline_repr():
    """Test pipeline repr."""
    pipeline = MockPipeline(name="test", agents=[])
    r = repr(pipeline)
    assert "MockPipeline" in r
    assert "test" in r


@pytest.mark.asyncio
async def test_hook_registration():
    """Test hook registration and execution."""
    pipeline = MockPipeline(name="test", agents=[])

    called = []

    async def hook(p, **kwargs):
        called.append("called")

    pipeline.register_hook("pre_pipeline", hook)
    await pipeline._run_hooks("pre_pipeline")

    assert len(called) == 1
    assert called[0] == "called"


@pytest.mark.asyncio
async def test_sync_hook():
    """Test synchronous hook works."""
    pipeline = MockPipeline(name="test", agents=[])

    called = []

    def hook(p, **kwargs):
        called.append("sync")

    pipeline.register_hook("pre_pipeline", hook)
    await pipeline._run_hooks("pre_pipeline")

    assert called == ["sync"]


@pytest.mark.asyncio
async def test_multiple_hooks():
    """Test multiple hooks on same type."""
    pipeline = MockPipeline(name="test", agents=[])

    order = []

    async def hook_a(p, **kwargs):
        order.append("a")

    async def hook_b(p, **kwargs):
        order.append("b")

    pipeline.register_hook("pre_pipeline", hook_a)
    pipeline.register_hook("pre_pipeline", hook_b)
    await pipeline._run_hooks("pre_pipeline")

    assert order == ["a", "b"]


@pytest.mark.asyncio
async def test_unregister_hook():
    """Test unregistering a hook."""
    pipeline = MockPipeline(name="test", agents=[])

    async def hook(p, **kwargs):
        pass

    pipeline.register_hook("pre_pipeline", hook)
    assert pipeline.unregister_hook("pre_pipeline", hook) is True
    assert pipeline.unregister_hook("pre_pipeline", hook) is False


@pytest.mark.asyncio
async def test_invalid_hook_type():
    """Test invalid hook type raises error."""
    pipeline = MockPipeline(name="test", agents=[])

    with pytest.raises(ValueError, match="Invalid hook_type"):
        pipeline.register_hook("invalid_hook", lambda: None)


@pytest.mark.asyncio
async def test_hook_error_does_not_abort():
    """Test that a failing hook does not crash the pipeline."""
    pipeline = MockPipeline(name="test", agents=[])

    called = []

    async def bad_hook(p, **kwargs):
        raise RuntimeError("boom")

    async def good_hook(p, **kwargs):
        called.append("ok")

    pipeline.register_hook("pre_pipeline", bad_hook)
    pipeline.register_hook("pre_pipeline", good_hook)
    await pipeline._run_hooks("pre_pipeline")

    assert called == ["ok"]


@pytest.mark.asyncio
async def test_status_transitions():
    """Test status transitions."""
    pipeline = MockPipeline(name="test", agents=[])

    assert pipeline.status == PipelineStatus.PENDING
    pipeline._set_status(PipelineStatus.RUNNING)
    assert pipeline.status == PipelineStatus.RUNNING
    pipeline._set_status(PipelineStatus.COMPLETED)
    assert pipeline.status == PipelineStatus.COMPLETED
