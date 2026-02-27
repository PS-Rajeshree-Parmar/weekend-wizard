# agent_fun.py
"""
Weekend Wizard — a friendly CLI agent that plans your weekend!

Usage:
    python agent_fun.py [path/to/server_fun.py]

Example prompts:
    Plan a cozy Saturday in New York at (40.7128, -74.0060). Include weather,
    2 mystery book ideas, one joke, and a dog pic.

    What's the weather right now at (37.7749, -122.4194)?

    Give me one trivia question.

    Plan a sci-fi weekend for Chicago.
"""

import asyncio
import json
import sys
from typing import Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── LLM helper ──────────────────────────────────────────────────────────────
# If Ollama is not installed, set USE_STUB = True to run with a hardcoded
# action sequence (good for testing the loop logic without a local LLM).
USE_STUB = False
STUB_ACTIONS = [
    {"action": "get_weather",  "args": {"latitude": 40.7128, "longitude": -74.0060}},
    {"action": "book_recs",    "args": {"topic": "mystery", "limit": 2}},
    {"action": "random_joke",  "args": {}},
    {"action": "random_dog",   "args": {}},
    {"action": "final",        "answer": "Here is your cozy weekend plan! (stub mode)"},
]
_stub_index = 0


def llm_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Call the local Ollama model and parse its JSON response."""
    if USE_STUB:
        global _stub_index
        action = STUB_ACTIONS[min(_stub_index, len(STUB_ACTIONS) - 1)]
        _stub_index += 1
        return action

    try:
        from ollama import chat  # type: ignore
    except ImportError:
        raise SystemExit(
            "ollama package not found. Run: pip install ollama\n"
            "Or set USE_STUB = True in agent_fun.py to run without Ollama."
        )

    resp = chat(
        model="mistral:7b",
        messages=messages,
        options={"temperature": 0.2},
    )
    txt = resp["message"]["content"].strip()

    # Strip markdown code fences if the model wrapped its JSON
    if txt.startswith("```"):
        txt = "\n".join(
            line for line in txt.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    try:
        return json.loads(txt)
    except Exception:
        # Ask the model to repair its own output
        from ollama import chat as _chat  # type: ignore
        fix = _chat(
            model="mistral:7b",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No explanation, no code fences."},
                {"role": "user",   "content": txt},
            ],
            options={"temperature": 0},
        )
        raw = fix["message"]["content"].strip()
        if raw.startswith("```"):
            raw = "\n".join(
                line for line in raw.splitlines()
                if not line.strip().startswith("```")
            ).strip()
        return json.loads(raw)


def llm_text(messages: List[Dict[str, str]]) -> str:
    """Call the model and return raw text (used for reflection)."""
    if USE_STUB:
        return "looks good"

    try:
        from ollama import chat  # type: ignore
    except ImportError:
        return "looks good"

    resp = chat(
        model="mistral:7b",
        messages=messages,
        options={"temperature": 0},
    )
    return resp["message"]["content"].strip()


# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM = """\
You are a cheerful weekend helper called Weekend Wizard. 🧙‍♂️

You have access to MCP tools. Use them to fetch real data before answering.
Think step-by-step (ReAct style):
  1. Decide which tool to call next, OR decide you have enough info to answer.
  2. Output ONLY a single JSON object — nothing else.

To call a tool:
  {"action": "<tool_name>", "args": {"param1": value1, ...}}

To give your final answer (after gathering data):
  {"action": "final", "answer": "Your friendly, concise reply here"}

Rules:
- Never mix prose and JSON. Output ONLY the JSON object.
- Do not call the same tool twice unless given new arguments.
- If the user mentions a city name but no coordinates, use city_to_coords first.
- Keep the final answer warm, brief, and reference the actual fetched data
  (e.g., the real temperature, book titles, joke text, dog image URL).
"""

REFLECTION_SYSTEM = """\
You are a careful proofreader. The assistant just wrote a final answer.
Check it:
  - Are any tool results mentioned but not actually used?
  - Are there obvious factual mistakes?
  - Is the tone friendly and concise?

If the answer looks correct and complete, reply with exactly: looks good
Otherwise, provide the corrected answer only (no explanation).
"""

# ── Main agentic loop ────────────────────────────────────────────────────────
async def main() -> None:
    server_path = sys.argv[1] if len(sys.argv) > 1 else "server_fun.py"

    print("\n🧙  Weekend Wizard is starting up…")
    print(f"   Server: {server_path}")
    print("   Type 'exit' or 'quit' to leave.\n")

    async with AsyncExitStack() as stack:
        # Spawn the MCP server as a subprocess over stdio
        stdio = await stack.enter_async_context(
            stdio_client(
                StdioServerParameters(command="python", args=[server_path])
            )
        )
        r_in, w_out = stdio
        session: ClientSession = await stack.enter_async_context(
            ClientSession(r_in, w_out)
        )
        await session.initialize()

        tools = (await session.list_tools()).tools
        tool_index = {t.name: t for t in tools}
        print("✅ Connected! Available tools:", list(tool_index.keys()), "\n")

        history: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM}
        ]

        while True:
            try:
                user = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Bye!")
                break

            if not user:
                continue
            if user.lower() in {"exit", "quit", "q"}:
                print("👋 Have a wonderful weekend!")
                break

            history.append({"role": "user", "content": user})
            called_tools: set = set()

            print()

            # ── Agentic loop (up to 8 steps) ──
            for step in range(8):
                try:
                    decision = llm_json(history)
                except Exception as e:
                    print(f"[LLM error] {e}")
                    history.append({
                        "role": "assistant",
                        "content": "Sorry, I had trouble understanding that. Could you rephrase?",
                    })
                    break

                action = decision.get("action", "")

                # ── Final answer ──
                if action == "final":
                    answer = decision.get("answer", "").strip()

                    # One-shot reflection
                    reflected = llm_text([
                        {"role": "system", "content": REFLECTION_SYSTEM},
                        {"role": "user",   "content": answer},
                    ])
                    if reflected.lower() != "looks good":
                        answer = reflected

                    print(f"🧙  Agent: {answer}\n")
                    history.append({"role": "assistant", "content": answer})
                    break

                # ── Tool call ──
                if action not in tool_index:
                    msg = f"(unknown tool '{action}' — skipping)"
                    print(f"   {msg}")
                    history.append({"role": "assistant", "content": msg})
                    continue

                # Deduplicate (avoid calling the same tool with identical args)
                call_key = (action, json.dumps(decision.get("args", {}), sort_keys=True))
                if call_key in called_tools:
                    msg = f"(tool '{action}' already called with these args — skipping)"
                    history.append({"role": "assistant", "content": msg})
                    continue
                called_tools.add(call_key)

                args = decision.get("args", {})
                print(f"   🔧 Calling tool: {action}({args})")

                try:
                    result = await session.call_tool(action, args)
                    if result.content:
                        payload = result.content[0].text
                    else:
                        payload = result.model_dump_json()
                except Exception as e:
                    payload = f"Error calling {action}: {e}"

                print(f"   📦 Result snippet: {payload[:120]}{'…' if len(payload) > 120 else ''}")
                history.append({
                    "role": "assistant",
                    "content": f"[tool:{action}] {payload}",
                })

            else:
                # Exceeded max steps
                print("🧙  Agent: I ran too many steps without finishing. Please try a simpler prompt.\n")


if __name__ == "__main__":
    asyncio.run(main())