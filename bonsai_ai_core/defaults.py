"""Static defaults shared by the CLI and Blender addon."""

PROVIDERS = ("openai", "anthropic", "google")

DEFAULT_MODELS = {
    "openai": "gpt-5.4",
    "anthropic": "claude-opus-4-6",
    "google": "gemini-2.5-flash-lite",
}

ENV_KEYS = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}

