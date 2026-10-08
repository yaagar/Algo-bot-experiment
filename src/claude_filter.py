"""The ONLY way this project calls Claude (spec §6.4, CLAUDE.md).

Each call runs the Claude Code CLI in print mode, with the Pro subscription login:
  * from an EMPTY sandbox folder outside the project (no CLAUDE.md, data or code visible);
  * with every tool disabled (--tools "" plus --disallowedTools as a second lock);
  * with user/project settings, hooks, plugins and MCP servers NOT loaded, so nothing
    from this machine's Claude Code setup leaks into the decision;
  * with the locked prompt as the system prompt and a strict JSON schema for the answer;
  * on the pinned model and effort, logged with every call.
Every response is cached by a hash of the exact input. If a call errors or takes over
60 s, the decision defaults to TAKE / TRADE_DAY and the failure is logged.
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from src.config import PROJECT_ROOT, load_settings

PROMPTS = PROJECT_ROOT / "prompts"
CACHE_DIR = PROJECT_ROOT / "data" / "processed" / "claude_cache"
LOG_PATH = PROJECT_ROOT / "data" / "processed" / "claude_calls.jsonl"

# Locked prompts (spec v1.6): SHA-256 of the file content with LF line endings
LOCKED = {
    "morning": ("morning_v1.md", "e0b1190373b6a716bc99e9a81303bcfba9583c27b726244661d9ffc83c3fc1c0"),
    "veto": ("veto_v1.md", "559615df6fc3dde4b8bc1e2d4a2c3bfa4e3ac836d76e9d28038c2a3825a12d59"),
}
DECISIONS = {"morning": ["TRADE_DAY", "NO_TRADE_DAY"], "veto": ["TAKE", "VETO"]}
DEFAULT_ON_FAILURE = {"morning": "TRADE_DAY", "veto": "TAKE"}
BLOCKED_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch",
                 "NotebookEdit", "Task", "Agent", "TodoWrite", "Skill"]


def schema_for(kind):
    return {"type": "object", "additionalProperties": False,
            "required": ["decision", "confidence", "reason"],
            "properties": {"decision": {"type": "string", "enum": DECISIONS[kind]},
                           "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                           "reason": {"type": "string"}}}


def prompt_text(kind):
    """The locked prompt, refusing to run if it differs from the approved version."""
    name, expected = LOCKED[kind]
    text = (PROMPTS / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{name} changed since it was locked (sha256 {actual}) - refusing to call Claude")
    return text


def config():
    c = load_settings()["claude"]
    return {"binary": c["cli_path"], "model": c["pinned_model"], "effort": c["effort"],
            "timeout": c["call_timeout_seconds"], "sandbox": Path(os.path.expandvars(c["sandbox_dir"]))}


def check_sandbox(sandbox):
    sandbox.mkdir(parents=True, exist_ok=True)
    if any(sandbox.iterdir()):
        raise RuntimeError(f"sandbox {sandbox} is not empty - refusing to call Claude")
    if PROJECT_ROOT in sandbox.resolve().parents or sandbox.resolve() == PROJECT_ROOT:
        raise RuntimeError("sandbox must be outside the project")


def run_cli(system_prompt, user_text, schema, cfg):
    """One raw CLI call. Returns (parsed CLI JSON or None, error text or None, seconds)."""
    check_sandbox(cfg["sandbox"])
    cmd = [cfg["binary"], "-p", "--model", cfg["model"], "--effort", cfg["effort"],
           "--output-format", "json", "--json-schema", json.dumps(schema),
           "--system-prompt", system_prompt,
           "--tools", "", "--disallowedTools", *BLOCKED_TOOLS,
           "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence"]
    t0 = time.time()
    try:
        out = subprocess.run(cmd, input=user_text, capture_output=True, text=True, encoding="utf-8",
                             cwd=cfg["sandbox"], timeout=cfg["timeout"])
    except subprocess.TimeoutExpired:
        return None, f"timeout after {cfg['timeout']}s", time.time() - t0
    try:
        return json.loads(out.stdout), None, time.time() - t0
    except json.JSONDecodeError:
        return None, f"unparseable output (exit {out.returncode}): {out.stdout[:300]} {out.stderr[:300]}", time.time() - t0


def cache_key(kind, user_text, cfg, recheck=False):
    material = json.dumps({"kind": kind, "prompt_sha": LOCKED[kind][1], "model": cfg["model"],
                           "effort": cfg["effort"], "input": user_text, "recheck": recheck}, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def decide(kind, user_text, meta=None, recheck=False):
    """Ask Claude for a morning (TRADE_DAY / NO_TRADE_DAY) or veto (TAKE / VETO) decision.

    recheck=True asks again with an independent cache entry (consistency check).
    Returns a dict with decision, confidence, reason, usage, failed, cached.
    """
    cfg = config()
    key = cache_key(kind, user_text, cfg, recheck)
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        rec["cached"] = True
        return rec

    raw, err, seconds = run_cli(prompt_text(kind), user_text, schema_for(kind), cfg)
    answer = None
    if raw is not None and not raw.get("is_error"):
        answer = raw.get("structured_output")
        if answer is None:
            try:
                answer = json.loads(raw.get("result", "").strip().strip("`").removeprefix("json").strip())
            except (json.JSONDecodeError, AttributeError):
                answer = None
        if not (isinstance(answer, dict) and answer.get("decision") in DECISIONS[kind]):
            err, answer = f"bad answer: {str(raw.get('result'))[:300]}", None
    elif raw is not None:
        err = f"CLI error: {raw.get('result')}"

    usage = (raw or {}).get("usage", {})
    rec = {
        "kind": kind, "key": key, "recheck": recheck, "model": cfg["model"], "effort": cfg["effort"],
        "prompt_sha": LOCKED[kind][1], "meta": meta or {},
        "decision": answer["decision"] if answer else DEFAULT_ON_FAILURE[kind],
        "confidence": answer.get("confidence") if answer else None,
        "reason": answer.get("reason") if answer else f"DEFAULTED: {err}",
        "failed": answer is None, "error": err, "seconds": round(seconds, 1),
        "usage": {k: usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                "cache_read_input_tokens", "output_tokens")},
        "cost_usd": (raw or {}).get("total_cost_usd"),
        "model_usage": (raw or {}).get("modelUsage"),
        "input_chars": len(user_text),
    }
    if not rec["failed"]:            # failures are not cached, so a re-run can retry them
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    rec["cached"] = False
    return rec
