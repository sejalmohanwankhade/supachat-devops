#!/usr/bin/env python3
"""
SupaChat DevOps Agent
─────────────────────
An AI-powered operations assistant that can:
  • Run health diagnostics
  • Summarize failed logs
  • Explain CI/CD failures
  • Restart containers safely
  • Perform RCA (root cause analysis)

Usage:
  python devops_agent.py health
  python devops_agent.py logs [--container NAME] [--lines N]
  python devops_agent.py restart [--container NAME]
  python devops_agent.py rca [--container NAME]
  python devops_agent.py cicd-explain <github_run_url>
  python devops_agent.py chat
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from typing import Optional

import anthropic

# ─── Config ───────────────────────────────────────────────────────────────────
COMPOSE_FILE = os.getenv("COMPOSE_FILE", "/opt/supachat/docker-compose.yml")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CONTAINERS = ["supachat-frontend", "supachat-backend", "supachat-nginx", "supachat-prometheus", "supachat-grafana"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

AGENT_SYSTEM = """You are a senior DevOps engineer for SupaChat, a conversational analytics platform.
You have deep expertise in:
- Docker / Docker Compose orchestration
- FastAPI + React application debugging
- Nginx reverse proxy configuration
- Prometheus / Grafana / Loki monitoring
- GitHub Actions CI/CD pipelines
- Linux system administration

When analyzing logs or errors:
1. Identify the root cause clearly
2. Explain the impact
3. Provide concrete remediation steps (with exact commands)
4. Suggest preventive measures

Be concise but thorough. Format responses with clear sections."""

# ─── Shell helpers ────────────────────────────────────────────────────────────

def run(cmd: str, capture: bool = True) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=capture,
        text=True, timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


def banner(text: str):
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def ask_claude(prompt: str, system: str = AGENT_SYSTEM) -> str:
    """Call Claude API and return response text."""
    if not client:
        return "[Claude API not configured — set ANTHROPIC_API_KEY]"
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_health():
    """Run comprehensive health diagnostics."""
    banner("🏥 SupaChat Health Diagnostics")
    results = {}

    # 1. Container status
    print("\n📦 Container Status:")
    rc, out, _ = run("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep supachat || echo 'No supachat containers running'")
    print(out)
    results["containers"] = out

    # 2. API health
    print("\n🌐 API Health:")
    rc, out, err = run("curl -sf http://localhost/health 2>&1")
    if rc == 0:
        try:
            data = json.loads(out)
            print(f"  Status: {data.get('status', 'unknown')}")
            print(f"  Supabase: {'✓' if data.get('supabase_connected') else '✗ (demo mode)'}")
            print(f"  LLM: {'✓' if data.get('llm_available') else '✗ (demo mode)'}")
            print(f"  Uptime: {data.get('uptime_seconds', 0):.0f}s")
            results["api"] = data
        except Exception:
            print(f"  Raw response: {out}")
    else:
        print(f"  ✗ API unreachable: {err}")
        results["api"] = "unreachable"

    # 3. Resource usage
    print("\n💻 Resource Usage:")
    rc, out, _ = run("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}' 2>/dev/null | grep supachat || echo 'N/A'")
    print(out)
    results["resources"] = out

    # 4. Disk space
    print("\n💾 Disk Space:")
    rc, out, _ = run("df -h / | tail -1")
    print(f"  {out.strip()}")

    # 5. Recent errors
    print("\n⚠️  Recent Errors (last 5 min):")
    rc, out, _ = run("docker logs supachat-backend --since 5m 2>&1 | grep -i 'error\\|exception\\|traceback' | tail -10 || echo '  None found'")
    print(out or "  None found")

    # 6. AI summary
    print("\n🤖 AI Diagnostics Summary:")
    summary = ask_claude(
        f"Analyze this health check data for SupaChat and provide a brief status summary with any concerns:\n\n{json.dumps(results, indent=2)}"
    )
    print(summary)


def cmd_logs(container: str = "supachat-backend", lines: int = 100):
    """Fetch and AI-summarize container logs."""
    banner(f"📋 Log Analysis: {container}")

    rc, logs, err = run(f"docker logs {container} --tail {lines} 2>&1")
    if rc != 0 and not logs:
        print(f"✗ Could not fetch logs: {err}")
        return

    print(f"\nFetched {lines} lines from {container}")
    print("\n🤖 AI Log Summary:\n")

    summary = ask_claude(
        f"""Analyze these Docker container logs from '{container}'. 
Identify:
1. Any errors or warnings
2. Performance issues
3. Unusual patterns
4. Recommended actions

LOGS:
{logs[-8000:]}  # Trim to avoid token limits
"""
    )
    print(summary)

    # Show raw tail
    print(f"\n📄 Raw Log Tail (last 20 lines):")
    rc, tail, _ = run(f"docker logs {container} --tail 20 2>&1")
    print(tail)


def cmd_restart(container: Optional[str] = None):
    """Safely restart one or all containers."""
    banner(f"🔄 Safe Restart: {container or 'all services'}")

    if container:
        targets = [container]
    else:
        targets = ["supachat-backend", "supachat-frontend", "supachat-nginx"]

    for svc in targets:
        print(f"\nRestarting {svc}...")
        rc, out, err = run(f"docker restart {svc}")
        if rc == 0:
            print(f"  ✓ {svc} restarted")
        else:
            print(f"  ✗ Failed to restart {svc}: {err}")

    # Wait and verify
    import time
    print("\nWaiting 10s for services to stabilize...")
    time.sleep(10)

    print("\n🔍 Post-restart health check:")
    cmd_health()


def cmd_rca(container: str = "supachat-backend"):
    """AI-powered root cause analysis."""
    banner(f"🔬 Root Cause Analysis: {container}")

    # Collect all evidence
    evidence = {}

    # Container inspect
    rc, out, _ = run(f"docker inspect {container} 2>&1")
    evidence["inspect"] = out[:3000] if out else "N/A"

    # Recent logs
    rc, out, _ = run(f"docker logs {container} --tail 200 2>&1")
    evidence["logs"] = out[-4000:] if out else "N/A"

    # Container events
    rc, out, _ = run(f"docker events --filter container={container} --since 1h --until 0s 2>&1 | tail -20 || echo 'N/A'")
    evidence["events"] = out

    # System resources
    rc, out, _ = run("free -m && df -h")
    evidence["system"] = out

    print("📊 Evidence collected. Running AI analysis...\n")

    rca = ask_claude(
        f"""Perform a root cause analysis for the container '{container}'.

Here is all available evidence:

CONTAINER INSPECT (truncated):
{evidence['inspect']}

RECENT LOGS:
{evidence['logs']}

DOCKER EVENTS:
{evidence['events']}

SYSTEM RESOURCES:
{evidence['system']}

Please provide:
1. **Root Cause**: What is the primary issue?
2. **Contributing Factors**: What made this worse?
3. **Impact Assessment**: What is affected?
4. **Immediate Fix**: Commands to run right now
5. **Long-term Prevention**: What to change to prevent recurrence
"""
    )
    print(rca)


def cmd_cicd_explain(log_text: str):
    """Explain a CI/CD failure from log text."""
    banner("🔧 CI/CD Failure Analysis")

    explanation = ask_claude(
        f"""A GitHub Actions CI/CD pipeline has failed. Analyze the following log output and:

1. Identify the exact point of failure
2. Explain what went wrong in plain English
3. Provide the exact fix (code changes, config changes, or commands)
4. Explain how to prevent this in the future

FAILURE LOG:
{log_text}
"""
    )
    print(explanation)


def cmd_chat():
    """Interactive DevOps chat session."""
    banner("💬 SupaChat DevOps Agent — Interactive Mode")
    print("Type 'exit' to quit, 'help' for commands\n")

    conversation = []

    # Gather context
    rc, ps_out, _ = run("docker ps --format '{{.Names}}\t{{.Status}}' | grep supachat 2>/dev/null || echo 'no containers'")
    rc, health_out, _ = run("curl -sf http://localhost/health 2>/dev/null || echo 'api unreachable'")

    system = f"""{AGENT_SYSTEM}

CURRENT SYSTEM STATE:
Docker Containers:
{ps_out}

API Health:
{health_out}

You can help the user with: health checks, log analysis, restarts, RCA, CI/CD debugging, Nginx config, Prometheus queries, etc.
"""

    while True:
        try:
            user_input = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if user_input.lower() == "help":
            print("  health     — run health diagnostics")
            print("  logs       — analyze recent logs")
            print("  restart    — restart containers")
            print("  rca        — root cause analysis")
            print("  Or just ask anything about the system!")
            continue

        # Handle shortcut commands
        if user_input == "health":
            cmd_health(); continue
        elif user_input.startswith("logs"):
            cmd_logs(); continue
        elif user_input.startswith("restart"):
            cmd_restart(); continue
        elif user_input.startswith("rca"):
            cmd_rca(); continue

        # AI conversation
        conversation.append({"role": "user", "content": user_input})

        if not client:
            print("[Set ANTHROPIC_API_KEY to enable AI responses]")
            continue

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system,
            messages=conversation,
        )
        reply = response.content[0].text
        conversation.append({"role": "assistant", "content": reply})
        print(f"\n🤖 {reply}")


# ─── CLI Entry ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SupaChat DevOps Agent — AI-powered operations automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("health", help="Run comprehensive health diagnostics")

    p_logs = sub.add_parser("logs", help="Fetch and AI-analyze container logs")
    p_logs.add_argument("--container", default="supachat-backend")
    p_logs.add_argument("--lines", type=int, default=100)

    p_restart = sub.add_parser("restart", help="Safely restart containers")
    p_restart.add_argument("--container", default=None)

    p_rca = sub.add_parser("rca", help="AI root cause analysis")
    p_rca.add_argument("--container", default="supachat-backend")

    p_cicd = sub.add_parser("cicd-explain", help="Explain CI/CD failure from log")
    p_cicd.add_argument("log", nargs="?", default=None, help="Log text (or pipe via stdin)")

    sub.add_parser("chat", help="Interactive DevOps chat")

    args = parser.parse_args()

    if args.command == "health":
        cmd_health()
    elif args.command == "logs":
        cmd_logs(args.container, args.lines)
    elif args.command == "restart":
        cmd_restart(args.container)
    elif args.command == "rca":
        cmd_rca(args.container)
    elif args.command == "cicd-explain":
        log_text = args.log or sys.stdin.read()
        cmd_cicd_explain(log_text)
    elif args.command == "chat":
        cmd_chat()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
