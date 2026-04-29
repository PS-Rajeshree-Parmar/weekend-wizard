import asyncio
import json
import sys
from typing import Dict, Any, List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat
import time

SYSTEM = (
    "You are a cheerful weekend helper.\n"
    "You can call MCP tools.\n\n"

    "AVAILABLE TOOLS (ONLY THESE TOOLS EXIST):\n"

    "1) book_recs(topic: string, limit: number)\n"
    "   - Use when the user asks for book ideas, book recommendations, reading suggestions, or books by topic.\n"

    "2) get_weather(lat: number, lon: number)\n"
    "   - Use ONLY when the user asks for current weather or temperature at a specific location.\n"
    "   - Latitude and longitude MUST be provided.\n"

    "3) random_joke()\n"
    "   - Use when the user asks for a joke or something funny.\n"

    "4) random_dog()\n"
    "   - Use when the user asks for a dog picture or dog image.\n"

    "5) trivia()\n"
    "   - Use when the user asks for a trivia question or quiz.\n\n"

    "TOOL USAGE RULES:\n"
    "- Never invent or assume tools that are not listed above.\n"
    "- If the user asks for book ideas, YOU MUST call book_recs.\n"
    "- If a required argument is missing, ask the user for it instead of guessing.\n"
    "- Call at most ONE tool per response.\n\n"

    "RESPONSE FORMAT RULES:\n"
    "- When calling a tool, respond with EXACTLY ONE valid JSON object:\n"
    "  {\"action\": \"<tool_name>\", \"args\": {...}}\n"
    "- When finished, respond with EXACTLY ONE valid JSON object:\n"
    "  {\"action\": \"final\", \"answer\": \"...\"}\n"
    "- Never output text outside JSON.\n"
    "- Never output multiple JSON objects.\n"
    "- No markdown.\n"
)

# -------------------- LLM Helpers --------------------

def extract_json(text: str):
    if not text or not text.strip():
        raise json.JSONDecodeError("Empty response", text, 0)

    text = text.strip()
    decoder = json.JSONDecoder()
    obj, idx = decoder.raw_decode(text)

    if not isinstance(obj, dict):
        raise json.JSONDecodeError("JSON is not an object", text, 0)

    return obj


def llm_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Calls the LLM and ensures a structured JSON response.
    Returns a dict with at least an "action" key.
    Handles numbers, lists, malformed JSON, and retries once if needed.
    """
    # -------------------- Step 1: Initial call --------------------
    resp = chat(
        model="mistral:7b",
        messages=messages,
        options={"temperature": 0.0},
    )
    content = resp["message"]["content"]

    # -------------------- Step 2: Try parsing JSON --------------------
    try:
        data = extract_json(content)
    except json.JSONDecodeError:
        # Ask model to strictly return JSON
        fix = chat(
            model="mistral:7b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return EXACTLY one JSON object with this schema:\n"
                        '{"action": "final", "answer": "<string>"}\n'
                        "No other output."
                    ),
                },
                {"role": "user", "content": messages[-1]["content"]},
            ],
            options={"temperature": 0},
        )

        try:
            data = extract_json(fix["message"]["content"])
        except json.JSONDecodeError:
            return {
                "action": "final",
                "answer": "⚠️ Model returned invalid output repeatedly."
            }

    # -------------------- Step 3: Handle scalar responses --------------------
    if isinstance(data, (int, float, str)):
        retry = chat(
            model="mistral:7b",
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "system", "content": (
                    "You MUST respond with a valid JSON object. Numbers or single tokens are invalid. "
                    "If the user asks for book ideas, call book_recs(topic, limit)."
                )},
                *messages,
            ],
            options={"temperature": 0},
        )
        try:
            data = extract_json(retry["message"]["content"])
        except json.JSONDecodeError:
            return {"action": "final", "answer": "⚠️ Model could not produce valid JSON. Please try again."}

    # -------------------- Step 4: Handle lists as multi-step plans --------------------
    if isinstance(data, list):
        return {
            "action": "plan",
            "steps": data
        }

    # -------------------- Step 5: Handle anything not dict --------------------
    if not isinstance(data, dict):
        return {
            "action": "final",
            "answer": str(data)
        }

    # -------------------- Step 6: Defensive recovery (dict missing action) --------------------
    if "action" not in data:
        return {
            "action": "final",
            "answer": data.get("message", str(data))
        }

    # -------------------- Step 7: Extra sanity check --------------------
    if not isinstance(data, dict):
        return {
            "action": "final",
            "answer": "⚠️ Model failed to return valid JSON. Please try again."
        }

    # -------------------- Step 8: Return clean JSON --------------------
    return data


def reflect_answer(answer: str, tool_context: str = "") -> str:
    reflect = chat(
        model="mistral:7b",
        messages=[
            {
                "role": "system",
                "content": (
                    "Check the answer against the tool result below.\n"
                    "Reply with ONLY one of the following:\n"
                    "1) looks good\n"
                    "2) a corrected final answer\n"
                    "Do NOT add anything else."
                ),
            },
            {"role": "system", "content": tool_context},
            {"role": "user", "content": answer},
        ],
        options={"temperature": 0},
    )

    content = reflect["message"]["content"].strip().lower()

    normalized = content.lstrip("0123456789). ").strip()

    if normalized == "looks good":
        return answer

    return reflect["message"]["content"].strip()


# -------------------- Tool Helpers --------------------

def format_tool_result(result) -> str:
    if result.content:
        return json.dumps(
            [c.model_dump() for c in result.content],
            ensure_ascii=False,
            indent=2,
        )
    return result.model_dump_json(indent=2)


# -------------------- Main Agent Loop --------------------

async def main():
    server_path = sys.argv[1] if len(sys.argv) > 1 else "server_fun.py"

    exit_stack = AsyncExitStack()
    try:
        stdio = await exit_stack.enter_async_context(
            stdio_client(
                StdioServerParameters(
                    command=sys.executable,
                    args=[server_path],
                )
            )
        )
        r_in, w_out = stdio

        session = await exit_stack.enter_async_context(
            ClientSession(r_in, w_out)
        )

        try:
            await session.initialize()
        except Exception:
            await exit_stack.aclose()
            raise

        tools = (await session.list_tools()).tools
        tool_index = {t.name: t for t in tools}

        print("Connected tools:", list(tool_index.keys()))

        history: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM}
        ]

        while True:
            user = input("\nYou: ").strip()
            # start_time = time.time()
            if not user or user.lower() in {"exit", "quit"}:
                break

            history.append({"role": "user", "content": user})

            seen_calls = set()

            last_tool_payload = ''

            for _ in range(4):  # bounded reasoning loop
                decision = llm_json(history)

                if decision["action"] not in tool_index and decision["action"] != "final":
                    print(f"\n⚠️ LLM tried unknown tool: {decision['action']}")
                    history.append({
                        "role": "assistant",
                        "content": "⚠️ Invalid tool requested by model."
                    })
                    break

                if decision["action"] == "final":
                    answer = decision.get("answer", "")

                    if last_tool_payload:   # 👈 ADD THIS
                        answer = reflect_answer(answer, last_tool_payload)

                    print("Agent:", answer)
                    history.append({"role": "assistant", "content": answer})
                    # print(time.time()-start_time)
                    break

                tname = decision["action"]
                args = decision.get("args", {})

                call_sig = (tname, json.dumps(args, sort_keys=True))
                if call_sig in seen_calls:
                    history.append({
                        "role": "assistant",
                        "content": "(tool call repeated; stopping)"
                    })
                    break
                seen_calls.add(call_sig)

                if tname not in tool_index:
                    history.append({
                        "role": "assistant",
                        "content": f"(unknown tool {tname})"
                    })
                    continue
                
                print(f"\n🔧 LLM called tool: {tname}")

                result = await session.call_tool(tname, args)
                payload = format_tool_result(result)

                last_tool_payload = payload

                history.append({
                    "role": "system",
                    "content": (
                        f"Tool `{tname}` returned the following result:\n"
                        f"{payload}"
                    )
                })


    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())
