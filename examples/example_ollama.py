"""Example: Using local Ollama models with Kiwis Research."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def check_ollama_health():
    """Check if Ollama server is running and list available models."""
    from kiwis.models.providers.ollama_provider import OllamaProvider
    
    provider = OllamaProvider()
    
    print("🔍 Checking Ollama health...")
    healthy = await provider._check_health()
    
    if not healthy:
        print("  ❌ Ollama is not reachable at localhost:11434")
        print("  💡 Start Ollama with: ollama serve")
        return False
    
    print("  ✅ Ollama is running!")
    return True


async def list_available_models():
    """List all models available in local Ollama."""
    from kiwis.models.providers.ollama_provider import OllamaProvider
    
    provider = OllamaProvider()
    
    print("\n📦 Available Ollama models:")
    try:
        models = await provider.list_models()
        for model in models:
            size_gb = model.size / (1024 ** 3) if model.size else "?"
            print(f"  • {model.name:<20} ({size_gb:.1f} GB)")
    except Exception as e:
        print(f"  ⚠️ Could not list models: {e}")
    
    return models


async def chat_with_ollama():
    """Chat with a local Ollama model."""
    from kiwis.models.providers.ollama_provider import OllamaProvider
    from kiwis.models.base import ChatMessage, ModelConfig
    
    provider = OllamaProvider()
    
    prompt = "Explain what Kiwis Research does in 3 sentences."
    config = ModelConfig(model_name="llama3.2", temperature=0.7, max_tokens=256)
    
    print(f"\n💬 Asking local model '{config.model_name}':")
    print(f"  \"{prompt[:60]}...\"\n")
    
    messages = [
        ChatMessage(role="system", content="You are a helpful research assistant."),
        ChatMessage(role="user", content=prompt),
    ]
    
    try:
        response = await provider.chat(messages, config)
        print(f"  Response:\n    {response.content}\n")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")


async def compare_provider_costs():
    """Compare cost per token between cloud and local providers."""
    
    cost_per_m_input = {
        "gpt-4o": 2.50,           # $2.50 per 1M input tokens
        "gpt-4o-mini": 0.15,      # $0.15 per 1M input tokens
        "claude-3.5-s": 3.00,     # $3.00 per 1M input tokens
        "deepseek-reasoner": 0.14,# $0.14 per 1M input tokens
        "ollama/local": 0.00,     # FREE — runs on your hardware!
    }
    
    print("\n💰 Cost comparison (per 1M input tokens):")
    print("-" * 50)
    for provider, cost in cost_per_m_input.items():
        label = "FREE" if cost == 0 else f"${cost:.2f}"
        print(f"  {provider:<20} {label:>10}")
    
    print("\n  💡 Local models save money but trade off:")
    print("     • Speed (GPU-dependent)")
    print("     • Quality vs. parameter count")
    print("     • Hardware requirements (RAM, GPU VRAM)")


async def run_research_with_ollama():
    """Configure and run the research pipeline using local Ollama models."""
    from kiwis.config.llm_providers import ProviderRegistry, LLMProviderConfig, LLMProviderType
    
    # Create a custom registry with Ollama as primary for certain agents
    registry = ProviderRegistry.with_defaults()
    
    print("\n🤖 Agent model assignments (hybrid cloud/local):")
    assignments = {
        "ideation": ("gpt-4o", "cloud"),
        "librarian": ("gpt-4o", "cloud"),
        "experiment_architect": ("mistral-nemo", "local"),
        "engineer": ("llama3.2", "local"),    # Code generation — runs locally!
        "data_analyst": ("qwen2.5-coder:7b", "local"),
        "writer": ("claude-3.5-sonnet-20241022", "cloud"),
        "reviewer": ("llama3.3", "local"),     # Can run locally with enough RAM!
    }
    
    print(f"  {'Agent':<25} {'Model':<25} {'Provider'}")
    print("  " + "-" * 60)
    for agent, (model, source) in assignments.items():
        print(f"  {agent:<25} {model:<25} {source}")


async def main():
    """Run all Ollama examples."""
    print("=" * 60)
    print("Kiwis Research — Ollama Local Models Integration")
    print("=" * 60)
    
    healthy = await check_ollama_health()
    if not healthy:
        print("\n⚠️ Ollama is not running. Install/start it:")
        print("  brew install ollama          # macOS")
        print("  ollama pull llama3.2         # Pull a model")
        print("  ollama serve                 # Start the server")
        return
    
    await list_available_models()
    await chat_with_ollama()
    await compare_provider_costs()
    await run_research_with_ollama()


if __name__ == "__main__":
    asyncio.run(main())
