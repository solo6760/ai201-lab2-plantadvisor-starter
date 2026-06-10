import json
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, MAX_TOOL_ROUNDS
from tools import lookup_plant, get_seasonal_conditions, search_plants_by_attribute, get_plant_list

_client = Groq(api_key=GROQ_API_KEY)

# ──────────────────────────────────────────────
# Tool definitions
#
# These are the schemas that tell the LLM what tools are available and how to
# call them. The LLM reads these descriptions and decides when (and how) to use
# each tool. They're already complete — your job is to implement the tool
# functions in tools.py and the agent loop below.
# ──────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_plant",
            "description": (
                "Look up care information for a specific houseplant by name. "
                "Returns detailed watering, light, humidity, and temperature requirements. "
                "Use this whenever the user asks about a specific plant."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plant_name": {
                        "type": "string",
                        "description": "The plant name to look up. Can be a common name, scientific name, or nickname (e.g., 'pothos', 'devil's ivy', 'Monstera deliciosa').",
                    }
                },
                "required": ["plant_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seasonal_conditions",
            "description": (
                "Get seasonal care adjustments for houseplants. "
                "Returns guidance on watering, fertilizing, light, and pests for the current or specified season. "
                "Use this when a user asks a season-specific question, or to complement plant care advice with seasonal context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "season": {
                        "type": "string",
                        "description": "The season to get care conditions for. If omitted, the current season is detected automatically.",
                        "enum": ["spring", "summer", "fall", "winter"],
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_plants_by_attribute",
            "description": (
                "Search and filter the plant database by care attributes such as light requirement "
                "and difficulty. Use this when a user asks for plant recommendations based on "
                "their home conditions (e.g., 'low light plants', 'easy to care for houseplants')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "light_requirement": {
                        "type": "string",
                        "description": "Filter by light level. Allowed values: 'low', 'moderate', 'bright'.",
                        "enum": ["low", "moderate", "bright"]
                    },
                    "difficulty": {
                        "type": "string",
                        "description": "Filter by difficulty. Allowed values: 'easy', 'moderate', 'hard'.",
                        "enum": ["easy", "moderate", "hard"]
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_plant_list",
            "description": "Get a list of all plant names and their difficulty levels present in the local database.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# ──────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a knowledgeable and friendly plant care advisor. "
    "Help users care for their houseplants by looking up specific plant information "
    "and current seasonal conditions using your available tools.\n\n"
    "Always use your tools to look up plant-specific information before answering — "
    "don't rely on your general knowledge alone. If a plant isn't in your database, "
    "say so clearly, check if it fits into a general category of plants we do have in "
    "the database (such as succulents or ferns), and offer care advice grounded in "
    "those categories where possible.\n\n"
    "Keep your advice practical and specific. Cite the source of your information "
    "when you have it (e.g., 'According to the care data for your monstera...')."
)

# ──────────────────────────────────────────────
# Tool dispatch
#
# This is already complete. It routes tool calls from the LLM to the actual
# Python functions in tools.py, and returns results as JSON strings (which is
# what the Groq API expects for tool results).
# ──────────────────────────────────────────────

def dispatch_tool(tool_name: str, tool_args: dict) -> str:
    """Route a tool call to the correct function and return the result as a JSON string."""
    print(f"  → Tool call: {tool_name}({tool_args})")
    if tool_name == "lookup_plant":
        result = lookup_plant(tool_args["plant_name"])
    elif tool_name == "get_seasonal_conditions":
        result = get_seasonal_conditions(tool_args.get("season"))
    elif tool_name == "search_plants_by_attribute":
        result = search_plants_by_attribute(
            light_requirement=tool_args.get("light_requirement"),
            difficulty=tool_args.get("difficulty")
        )
    elif tool_name == "get_plant_list":
        result = get_plant_list()
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
    print(f"  ← Result: {json.dumps(result)[:120]}{'...' if len(json.dumps(result)) > 120 else ''}")
    return json.dumps(result)


# ──────────────────────────────────────────────
# Agent loop
def run_agent(user_message: str, history: list) -> str:
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        for item in history:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                # Legacy format: list of [user, assistant] pairs
                user_msg, assistant_msg = item
                messages.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    messages.append({"role": "assistant", "content": assistant_msg})
            elif hasattr(item, "role") and hasattr(item, "content"):
                # Gradio ChatMessage object format
                messages.append({"role": item.role, "content": item.content})
            elif isinstance(item, dict) and "role" in item and "content" in item:
                # Dict format (commonly used in API/JSON formats)
                messages.append({"role": item["role"], "content": item["content"]})

        messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ROUNDS):
            response = _client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            if not response.choices or not response.choices[0].message:
                return "I'm sorry, I received an empty response from the model. Please try again."

            assistant_message = response.choices[0].message

            if not assistant_message.tool_calls:
                return assistant_message.content or "I'm sorry, I couldn't generate a text response."

            # The API requires appending the assistant message with tool calls first
            messages.append(assistant_message)

            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                except (json.JSONDecodeError, TypeError):
                    tool_args = {}
                
                tool_result = dispatch_tool(tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

        # If MAX_TOOL_ROUNDS is reached, make one final call without tools to get a text response
        final_response = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
        )
        if final_response.choices and final_response.choices[0].message:
            return final_response.choices[0].message.content or "I have reached the limit of tool usage for this turn."
        return "I have reached the limit of tool usage for this turn."

    except Exception as e:
        print(f"Agent Loop Error: {e}")
        return "I'm sorry, I encountered an unexpected error while processing your request. Please try again."
