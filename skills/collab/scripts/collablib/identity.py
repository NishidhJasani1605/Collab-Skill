"""Conservative host metadata; no model guesses, config defaults, or process scraping."""
import os
import re


ALIASES = {
    "codex": ("codex", "openai-codex", "codex-desktop", "codex-cli", "codex-ide", "openai-codex-desktop", "openai-codex-cli", "openai-codex-ide"),
    "antigravity": ("antigravity", "google-antigravity", "antigravity-ide", "antigravity-app", "antigravity-cli", "antigravity-desktop", "google-antigravity-ide", "google-antigravity-desktop"),
    "claude-code": ("claude-code",), "cursor": ("cursor",),
    "gemini-cli": ("gemini-cli",), "kimi-code": ("kimi-code",), "opencode": ("opencode",),
}


def platform_key(value):
    normalized = re.sub(r"[\s_]+", "-", value.strip().lower())
    return next((key for key, aliases in ALIASES.items() if normalized in aliases), "unknown")


def host_metadata(env=None):
    """Only active-session markers establish a host. Installed directories do not.

    COLLAB_HOST_* is an optional adapter contract, not a vendor environment API.
    Adapters must supply current-session values, never global config defaults.
    """
    env = os.environ if env is None else env
    candidates = []
    if env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID"):
        candidates.append(("codex", "Codex Desktop" if env.get("CODEX_APP_TOOLS_PIPE_PATH") else "Codex"))
    if env.get("ANTIGRAVITY_APP") or env.get("ANTIGRAVITY_CLI"):
        candidates.append(("antigravity", "Google Antigravity CLI" if env.get("ANTIGRAVITY_CLI") else "Google Antigravity"))
    result = {"platform": "unknown", "ide_name": "unknown", "model": "unknown", "reasoning_level": "unknown"}
    if len(candidates) == 1:
        result["platform"], result["ide_name"] = candidates[0]
    for field in result:
        value = env.get("COLLAB_HOST_" + field.upper())
        if value and value.strip():
            result[field] = value
    return result
