"""Default model IDs per provider (checked November 2026).

Change them here (or per agent in ``kiwis_config.yaml``) when providers retire models. Retirement notes:
- OpenAI shuts down gpt-4o / gpt-4o-mini / gpt-4.1 on 2027-01-14 (gpt-4-turbo already on 2026-10-23).
- Anthropic's Claude 3.x models are retired.
- DeepSeek retired ``deepseek-chat`` / ``deepseek-reasoner`` on 2026-07-24.
"""

OPENAI_MODELS = ["gpt-6.2-sol", "gpt-6.2-astra", "gpt-6.1-terra", "gpt-6-luna"]
ANTHROPIC_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
DEEPSEEK_MODELS = ["deepseek-v4-pro", "deepseek-flash"]

DEFAULT_OPENAI_MODEL = OPENAI_MODELS[0]
DEFAULT_ANTHROPIC_MODEL = ANTHROPIC_MODELS[0]
DEFAULT_DEEPSEEK_MODEL = DEEPSEEK_MODELS[0]

# Model used when neither the agent config nor the provider names one
DEFAULT_MODEL = DEFAULT_OPENAI_MODEL

# Room for reasoning plus a full JSON answer: current OpenAI and Claude models think before answering,
# and those thinking tokens count against this limit.
DEFAULT_MAX_TOKENS = 32000
