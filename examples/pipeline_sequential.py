# -*- coding: utf-8 -*-
"""Example: Sequential Pipeline for report generation."""

import asyncio
from agentscope.message import Msg
from copaw.pipeline import SequentialPipeline


async def log_step(pipeline, agent, step, msg, **kwargs):
    """Hook to log each step."""
    agent_id = getattr(agent, "agent_id", "unknown")
    print(f"[{pipeline.name}] Step {step}: {agent_id}")


async def main():
    # Create pipeline
    pipeline = SequentialPipeline(
        name="report_generation",
        agents=[],  # Add your agents here
    )

    # Register hook
    pipeline.register_hook("pre_agent_call", log_step)

    # Execute
    initial_msg = Msg(
        name="user",
        content="Analyze Q4 2024 sales data",
        role="user",
    )

    result = await pipeline.execute(msg=initial_msg)
    print(f"\nFinal result: {result.content}")


if __name__ == "__main__":
    asyncio.run(main())
