# Weekend Wizard 🧙‍♂️

A friendly CLI agent that helps you plan your weekend using AI! It fetches real-time weather, book recommendations, jokes, dog pictures, and trivia questions through MCP (Model Context Protocol) tools.

## What It Does

Weekend Wizard is a **real AI agent** that:
- ✅ Decides which tools to call based on your request
- ✅ Fetches live data from free, no-key APIs
- ✅ Runs completely locally using Ollama
- ✅ Uses reflection to double-check its answers

### Available Tools
- **Weather** — Current conditions via Open-Meteo
- **Book Recommendations** — Topic-based search via Open Library
- **Jokes** — Safe one-liners via JokeAPI
- **Dog Photos** — Random dog image URLs via Dog CEO API
- **Trivia** — Multiple-choice questions via Open Trivia DB
- **City to Coordinates** — Convert city names to lat/long (bonus feature!)

---

## Prerequisites

- **Python 3.10 or higher**
- **Windows, macOS, or Linux**
- **4 GB free disk space** (for the AI model)
- **Internet connection** (for API calls and initial setup)

---

## Installation & Setup

### Step 1: Download the Files

Download these two Python files:
- `server_fun.py` — MCP tools server
- `agent_fun.py` — Agent client with ReAct loop

Place them in a folder called `weekend-wizard`.

---

### Step 2: Set Up Python Environment

Open a terminal in the `weekend-wizard` folder and run:

#### On Windows:
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### On macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` at the start of your terminal prompt.

---

### Step 3: Install Python Packages

With the virtual environment active, run:

```bash
pip install "mcp>=1.2" requests ollama
```

Wait for the installation to complete (you'll see "Successfully installed...").

---

### Step 4: Install Ollama & Download the Model

1. Go to **https://ollama.com** and download Ollama for your operating system
2. Install it and restart your computer if prompted
3. Open a terminal and run:

```bash
ollama pull mistral:7b
```

This downloads the Mistral 7B model (~4.4 GB). Wait until you see "success".

---

## Running the Agent

### Start the Agent

In your terminal (with `.venv` active), run:

```bash
python agent_fun.py server_fun.py
```

You should see:
```
🧙  Weekend Wizard is starting up…
✅ Connected! Available tools: ['get_weather', 'book_recs', 'random_joke', 'random_dog', 'trivia', 'city_to_coords']

You:
```

---

## Example Prompts

Try these prompts to test the agent:

### Complete Weekend Plan
```
Plan a cozy Saturday in New York at (40.7128, -74.0060) with mystery books, a joke and a dog pic.
```

### Weather Only
```
What's the weather right now in San Francisco at (37.7749, -122.4194)?
```

### Using City Names (No Coordinates Needed)
```
What's the temperature in Chicago right now?
```

### Books + Entertainment
```
Give me 3 sci-fi book recommendations and a trivia question.
```

### Just for Fun
```
Tell me a joke and show me a cute dog picture.
```

---

## How It Works

### The Agent Loop (ReAct Style)

1. **User inputs a prompt** → Agent receives the request
2. **Agent decides** → Should I call a tool or answer directly?
3. **Tool call** → Agent calls the appropriate MCP tool
4. **Observe result** → Agent sees the real data returned
5. **Repeat or finish** → Agent decides if it needs more tools or can answer
6. **Reflection** → Before replying, the agent checks its own answer for mistakes
7. **Final answer** → User gets a friendly response with real data

### Architecture

```
User <--> agent_fun.py (Agent Client)
              |
              v
         MCP Protocol (stdio)
              |
              v
         server_fun.py (Tools Server)
         |    |    |    |    |
         |    |    |    |    +-- trivia (Open Trivia DB)
         |    |    |    +------- dog photos (Dog CEO)
         |    |    +------------ jokes (JokeAPI)
         |    +----------------- books (Open Library)
         +---------------------- weather (Open-Meteo)
         +---------------------- city coords (Open-Meteo Geocoding)
```

---

## Project Structure

```
weekend-wizard/
├── .venv/              # Virtual environment (auto-created)
├── server_fun.py       # MCP tools server (6 tools)
├── agent_fun.py        # Agent client (ReAct loop + LLM)
└── README.md           # This file
```

---

## Troubleshooting

### Problem: `ModuleNotFoundError: No module named 'mcp'`
**Fix:** Make sure your virtual environment is active (you see `.venv` in the prompt), then run:
```bash
pip install "mcp>=1.2" requests ollama
```

---

### Problem: `ollama: command not found`
**Fix:** 
1. Make sure Ollama is installed from https://ollama.com
2. Restart your terminal/computer after installing
3. Run `ollama pull mistral:7b` again

---

### Problem: Agent doesn't call tools, just makes up answers
**Fix:** The model needs stricter prompting. Open `agent_fun.py` and replace the `SYSTEM` variable (around line 60) with this:

```python
SYSTEM = """\
You are Weekend Wizard. You MUST call tools before answering. NEVER make up data.

STRICT RULES:
- You MUST call tools to get real data. Never invent weather, books, jokes, or dog photos.
- Output ONLY a single raw JSON object. No text before or after. No markdown. No explanation.

To call a tool:
{"action": "tool_name", "args": {"param": value}}

After all tools are called:
{"action": "final", "answer": "your reply with REAL data"}
"""
```

Save and run again.

---

### Problem: JSON parsing errors or malformed output
**Fix:** The agent has built-in JSON repair. If it still fails:
1. Try a simpler prompt
2. Check that the model downloaded correctly: `ollama list` (should show `mistral:7b`)
3. Try lowering the temperature in `agent_fun.py` (change `0.2` to `0.1`)

---

### Problem: Network/timeout errors when calling tools
**Fix:** The APIs are free and public but can be slow. Just retry. All tools have 20-second timeouts.

---

## Running Without Ollama (Testing Mode)

If you can't install Ollama right now, you can still test the agent logic:

1. Open `agent_fun.py`
2. Change line 28 from `USE_STUB = False` to `USE_STUB = True`
3. Run `python agent_fun.py server_fun.py`

The agent will use a hardcoded action sequence instead of calling the LLM. This lets you verify that the MCP tools and loop work correctly.

---

## Advanced Usage

### Testing Individual Tools (Optional)

Install the MCP Inspector to test tools without running the agent:

```bash
npx @modelcontextprotocol/inspector
```

Add a STDIO connection with command: `python server_fun.py`

---

### Changing the AI Model

You can use any Ollama model. Edit `agent_fun.py` and change both occurrences of:
```python
model="mistral:7b"
```

To another model like:
```python
model="llama3.2:3b"     # Smaller, faster
model="qwen2.5:7b"      # Better reasoning
model="mixtral:8x7b"    # Larger, more capable (requires more RAM)
```

First pull the new model: `ollama pull llama3.2:3b`

---

### Adjusting Model Temperature

In `agent_fun.py`, find the `llm_json()` function and change:
```python
options={"temperature": 0.2}
```

- **Lower (0.0–0.1):** More consistent, deterministic
- **Higher (0.3–0.5):** More creative, varied responses

---

## Stretch Goals (Optional Enhancements)

Want to extend the project? Try these:

1. **Save user preferences** — Store favorite topics in a JSON file
2. **Add rate limiting** — Implement backoff/retry for API calls
3. **Web UI** — Create a simple Flask/FastAPI frontend
4. **More tools** — Add movie search, recipe finder, news headlines
5. **Multi-turn conversations** — Make the agent remember context across prompts

---

## What You'll Learn

By completing this project, you'll understand:
- ✅ **Agentic AI** — How LLMs decide which actions to take
- ✅ **MCP (Model Context Protocol)** — Decoupling tools from the host
- ✅ **ReAct pattern** — Reason → Act → Observe loops
- ✅ **Local LLMs** — Running AI models on your own machine
- ✅ **Reflection** — Self-checking to improve accuracy
- ✅ **API integration** — Working with free public APIs

---

## License

This is an educational project. Feel free to modify and extend it!

---

## Support

Having trouble? Common fixes:
1. Make sure `.venv` is active before running commands
2. Check that Ollama is running: `ollama list` should work
3. Verify Python version: `python --version` (must be 3.10+)
4. Try restarting your terminal after installing Ollama

---

## Example Session

```
You: Plan a cozy Saturday in New York at (40.7128, -74.0060) with mystery books, a joke and a dog pic.

   🔧 Calling tool: get_weather({'latitude': 40.7128, 'longitude': -74.006})
   📦 Result snippet: {"time":"2025-02-27T10:00","temperature_2m":8.5,"weather_code":2,"wind_speed_10m":12.4}

   🔧 Calling tool: book_recs({'topic': 'mystery', 'limit': 2})
   📦 Result snippet: {"topic":"mystery","results":[{"title":"The Murder of Roger Ackroyd","author":"Agatha Christie",...

   🔧 Calling tool: random_joke({})
   📦 Result snippet: {"joke":"Why don't scientists trust atoms? Because they make up everything!"}

   🔧 Calling tool: random_dog({})
   📦 Result snippet: {"message":"https://images.dog.ceo/breeds/terrier-australian/n02096294_4492.jpg","status":"success"}

🧙  Agent: Here's your cozy Saturday plan! It's currently 8.5°C with partly cloudy skies in NYC. 
For mystery reads, check out "The Murder of Roger Ackroyd" by Agatha Christie or "Big Little Lies" 
by Liane Moriarty. Need a laugh? Why don't scientists trust atoms? Because they make up everything! 
And here's an adorable pup to brighten your day: https://images.dog.ceo/breeds/terrier-australian/n02096294_4492.jpg

Enjoy your weekend! 🐶📚
```

---

Happy weekend planning! 🧙‍♂️✨
