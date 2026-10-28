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
    host_session_id = "unknown"
    if env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID") or env.get("CODEX_APP_TOOLS_PIPE_PATH"):
        candidates.append(("codex", "Codex Desktop" if env.get("CODEX_APP_TOOLS_PIPE_PATH") else "Codex"))
        host_session_id = env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID") or "unknown"
    if (env.get("ANTIGRAVITY_AGENT") or env.get("ANTIGRAVITY_APP") or env.get("ANTIGRAVITY_CLI")
            or env.get("ANTIGRAVITY_CONVERSATION_ID") or env.get("ANTIGRAVITY_TRAJECTORY_ID")
            or env.get("ANTIGRAVITY_APP_DATA_DIR")):
        candidates.append(("antigravity", "Google Antigravity CLI" if env.get("ANTIGRAVITY_CLI") else "Google Antigravity"))
        host_session_id = env.get("ANTIGRAVITY_CONVERSATION_ID") or env.get("ANTIGRAVITY_TRAJECTORY_ID") or "unknown"
    if env.get("CURSOR_TRACE_ID"):
        candidates.append(("cursor", "Cursor"))
        host_session_id = env.get("CURSOR_TRACE_ID") or "unknown"
    if env.get("CLAUDECODE") or env.get("CLAUDE_CODE_ENTRYPOINT") or env.get("ANTHROPIC_CLAUDE_CODE"):
        candidates.append(("claude-code", "Claude Code"))
        host_session_id = env.get("CLAUDE_CONVERSATION_ID") or env.get("CLAUDE_SESSION_ID") or "unknown"

    model = "unknown"
    reasoning_level = "unknown"
    if len(candidates) == 1:
        plat = candidates[0][0]
        if plat == "codex":
            model = env.get("CODEX_MODEL") or env.get("OPENAI_MODEL") or "unknown"
            reasoning_level = env.get("CODEX_REASONING_EFFORT") or env.get("CODEX_REASONING_LEVEL") or "unknown"
        elif plat == "antigravity":
            model = env.get("ANTIGRAVITY_MODEL") or env.get("GEMINI_MODEL") or "unknown"
            reasoning_level = env.get("ANTIGRAVITY_REASONING_EFFORT") or env.get("ANTIGRAVITY_REASONING_LEVEL") or "unknown"
        elif plat == "claude-code":
            model = env.get("CLAUDE_MODEL") or env.get("ANTHROPIC_MODEL") or "unknown"
        elif plat == "cursor":
            model = env.get("CURSOR_MODEL") or "unknown"

    if host_session_id == "unknown" and len(candidates) == 1:
        try:
            ppid = os.getppid()
            if ppid > 0:
                host_session_id = f"proc-{ppid}"
        except (AttributeError, OSError):
            pass

    result = {
        "platform": "unknown",
        "ide_name": "unknown",
        "model": model,
        "reasoning_level": reasoning_level,
        "host_session_id": host_session_id if len(candidates) == 1 else "unknown",
    }
    if len(candidates) == 1:
        result["platform"], result["ide_name"] = candidates[0]
    for field in ("platform", "ide_name", "model", "reasoning_level", "host_session_id"):
        value = env.get("COLLAB_HOST_" + field.upper())
        if value and value.strip():
            result[field] = value
    return result
