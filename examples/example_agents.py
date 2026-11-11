"""Example: Using individual agents."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def example_ideation_agent():
    """Demonstrate the Ideation agent."""
    from kiwis.agents import IdeationAgent
    from kiwis.agents.base import AgentContext
    
    print("🔍 Testing Ideation Agent...")
    
    agent = IdeationAgent()
    context = AgentContext(research_topic="Graph neural networks for drug discovery")
    
    output = await agent.execute(context)
    print(f"  Status: {output.state.value}")
    print(f"  Data keys: {list(output.data.keys())[:3]}")
    return output


async def example_librarian_agent():
    """Demonstrate the Librarian agent."""
    from kiwis.agents import LibrarianAgent
    from kiwis.agents.base import AgentContext
    
    print("\n📚 Testing Librarian Agent (arXiv + Semantic Scholar)...")
    
    agent = LibrarianAgent()
    context = AgentContext(research_topic="self-supervised learning medical imaging")
    
    output = await agent.execute(context)
    print(f"  Status: {output.state.value}")
    papers = output.data.get("num_papers_found", 0)
    print(f"  Papers found via APIs: {papers}")
    return output


async def example_agent_swarm():
    """Demonstrate multi-agent collaboration."""
    from kiwis.orchestrator.swarm import AgentSwarm
    
    print("\n🤖 Testing Agent Swarm Communication...")
    
    swarm = AgentSwarm()
    
    # Register agents
    from kiwis.agents import IdeationAgent, LibrarianAgent
    
    ideation_agent = IdeationAgent()
    librarian_agent = LibrarianAgent()
    
    swarm.register_agent("ideation", ideation_agent)
    swarm.register_agent("librarian", librarian_agent)
    
    # Broadcast research topic
    notified = await swarm.broadcast(
        content={"topic": "federated learning privacy"},
        from_agent="orchestrator",
    )
    
    print(f"  Notified agents: {notified}")
    print(f"  Shared state: {swarm.get_shared_state()}")


async def main():
    """Run all agent examples."""
    try:
        await example_ideation_agent()
        await example_librarian_agent()
        await example_agent_swarm()
    except Exception as e:
        print(f"\n⚠️ Agent example error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
