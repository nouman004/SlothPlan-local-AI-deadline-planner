"""Local LLM via Ollama's REST API. The model only decomposes + estimates; it never does clock math."""
import json
import requests

OLLAMA = "http://localhost:11434/api/chat"


class LLMError(Exception):
    """Friendly, user-facing error."""


SYSTEM = """You break a task into subtasks and estimate realistic minutes for each.
Return ONLY JSON: {"subtasks":[{"title":str,"minutes":int}]}
Rules:
- 2-6 subtasks, in the exact order they must be done.
- Titles: max 6 words.
- Merge similar steps into ONE subtask. Never repeat a step per item.
- Be lean: focused work, no padding. Small tasks get few, short subtasks.
- Each subtask between 5 and 90 minutes.
- Do not mention clock times or deadlines."""


def _chat(payload, model):
    try:
        r = requests.post(OLLAMA, json=payload, timeout=180)
        if r.status_code == 404:
            raise LLMError(f"Model '{model}' not found. Run: ollama pull {model}")
        r.raise_for_status()
        return r.json()["message"]["content"]
    except requests.ConnectionError:
        raise LLMError("Can't reach Ollama. Start the Ollama app (or run `ollama serve`) and try again.")
    except requests.Timeout:
        raise LLMError("Ollama timed out. The model may still be loading. Try again in a minute.")
    except requests.RequestException as e:
        raise LLMError(f"Ollama error: {e}")


def breakdown(task: str, model: str = "qwen2.5:7b"):
    content = _chat({
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0, "seed": 42},   # same task -> same plan
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Task: {task}"}],
    }, model)
    try:
        subs = json.loads(content)["subtasks"]
        out = [{"title": str(s["title"])[:80], "minutes": min(90, max(5, int(s["minutes"])))} for s in subs]
    except (ValueError, KeyError, TypeError):
        raise LLMError("The model returned something unreadable. Try again or try a bigger model.")
    if not out:
        raise LLMError("The model returned no subtasks. Try rephrasing the task.")
    return out


def rest_ideas(minutes: int, model: str = "qwen2.5:7b"):
    return _chat({
        "model": model, "stream": False, "options": {"temperature": 0.8},
        "messages": [{"role": "user", "content":
            f"I have {minutes} minutes of guilt-free rest before a deadline. "
            "Give 3 one-line restful ideas, in the voice of a calm sloth. No fluff."}],
    }, model)