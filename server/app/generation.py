"""LLM-backed generation helpers using the Groq API (settings.llm_api_key).

All functions are best-effort: they return a usable fallback if the API call
fails so the learning flow never halts on a network error.
"""

import json
import logging
import urllib.request

from .config import Settings
from .data import Library, Problem

log = logging.getLogger("relearn")


# --- shared Groq helper -----------------------------------------------------

def _groq_chat(settings: Settings, messages: list[dict], *, temperature: float = 0.3, response_format: dict | None = None) -> str | None:
    """Send a chat completion request to Groq. Returns the text content or None on failure."""
    payload: dict = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "relearn/1.0",
        },
        data=json.dumps(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=15.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        log.error("Groq API call failed: %s", exc)
        return None


# --- misconception generation -----------------------------------------------

def generate_misconception(settings: Settings, problem: Problem, student_response: str, student_explanation: str) -> str:
    prompt = (
        "You are an expert computer science teacher diagnosing student misconceptions.\n"
        "A student has provided an incorrect answer to the following problem.\n\n"
        f"Problem Topic: {problem.topic}\n"
        f"Problem Description:\n{problem.problem_text}\n\n"
        f"Student Answer: {student_response}\n"
        f"Student Explanation: {student_explanation}\n\n"
        "Describe the underlying misconception the student likely has. Keep it to a single, clear sentence starting with a verb (e.g., 'Believes that...'). Do not include any introductory text or quotes, just the misconception."
    )
    result = _groq_chat(settings, [{"role": "user", "content": prompt}])
    if result:
        return result
    return f"Unknown misconception on {problem.topic}: {student_response[:20]}..."


# --- probe generation -------------------------------------------------------

def generate_probe_problem(
    settings: Settings,
    library: Library,
    original_problem: Problem,
    misconception_a_id: str,
    misconception_b_id: str,
) -> dict | None:
    """Generate a short Python predict_output problem that differentiates two misconceptions.

    Returns a dict with keys: problem_text, correct_output, predictions{a_id: str, b_id: str}
    or None if generation fails.
    """
    try:
        m_a = library.misconception(misconception_a_id)
        m_b = library.misconception(misconception_b_id)
    except KeyError:
        return None

    prompt = (
        "You are a Python teacher designing a diagnostic question.\n\n"
        "Two students have different misconceptions about Python. Design a SHORT Python snippet "
        "(3-8 lines) that a student would be asked to predict the output of.\n"
        "The snippet must produce DIFFERENT outputs depending on which misconception a student holds.\n\n"
        f"Original problem topic: {original_problem.topic}\n"
        f"Original problem:\n{original_problem.problem_text}\n\n"
        f"Misconception A ({misconception_a_id}): {m_a.description}\n"
        f"Misconception B ({misconception_b_id}): {m_b.description}\n\n"
        "Requirements:\n"
        "- The snippet must be valid Python 3 that runs without errors.\n"
        "- The snippet must produce different visible output for each misconception.\n"
        "- Keep it short and focused; no imports needed.\n"
        "- Provide the REAL Python output, and what a student with each misconception would predict.\n\n"
        "Respond with ONLY a JSON object in this format:\n"
        "{\n"
        '  "problem_text": "the Python code snippet as a string",\n'
        '  "correct_output": "the actual Python output",\n'
        f'  "prediction_a": "what a student with misconception A would predict",\n'
        f'  "prediction_b": "what a student with misconception B would predict"\n'
        "}"
    )
    content = _groq_chat(
        settings,
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    if not content:
        return None
    try:
        data = json.loads(content)
        if not all(k in data for k in ("problem_text", "correct_output", "prediction_a", "prediction_b")):
            return None
        return {
            "problem_text": str(data["problem_text"]),
            "correct_output": str(data["correct_output"]),
            "predictions": {
                misconception_a_id: str(data["prediction_a"]),
                misconception_b_id: str(data["prediction_b"]),
            },
        }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.error("Failed to parse probe generation response: %s", exc)
        return None


# --- explanation generation -------------------------------------------------

def generate_explanation(
    settings: Settings,
    problem: Problem,
    misconception_id: str,
    misconception_description: str,
    student_response: str,
    student_explanation: str,
) -> str:
    """Generate a targeted explanation for the diagnosed misconception.

    Returns the explanation text (possibly with paragraph breaks).
    """
    prompt = (
        "You are an expert Python teacher. A student answered a Python problem incorrectly.\n\n"
        f"Problem:\n{problem.problem_text}\n\n"
        f"Correct output: {problem.correct_output or '(code problem)'}\n"
        f"Student's answer: {student_response}\n"
        f"Student's reasoning: {student_explanation}\n\n"
        f"The diagnosed misconception: {misconception_description}\n"
        f"(ID: {misconception_id})\n\n"
        "Write a targeted explanation (2-4 paragraphs) that:\n"
        "1. Clearly explains what the student misunderstood about Python.\n"
        "2. Shows why their reasoning was incorrect using the original problem.\n"
        "3. Gives a short corrected example or trace that demonstrates correct Python behavior.\n"
        "4. Is encouraging and clear — written directly to the student.\n\n"
        "Write only the explanation text. No headers, no bullet points. Use paragraph breaks (blank lines) between paragraphs."
    )
    result = _groq_chat(settings, [{"role": "user", "content": prompt}], temperature=0.5)
    if result:
        return result
    return (
        f"Your answer suggests you may believe: \"{misconception_description}\"\n\n"
        "Python does not work this way. Review how Python executes this kind of code step by step, "
        "paying attention to the order of operations and what each statement actually does."
    )


# --- retest problem generation ----------------------------------------------

def generate_retest_problems(
    settings: Settings,
    library: Library,
    original_problem: Problem,
    misconception_id: str,
    misconception_description: str,
    count: int = 2,
) -> list[dict]:
    """Generate retest problems that specifically test whether the misconception is fixed.

    Returns a list of dicts with keys: problem_text, correct_output, topic, item_type.
    Falls back to an empty list on failure (caller should pull from problem bank instead).
    """
    prompt = (
        f"You are a Python teacher. A student had this misconception:\n"
        f'"{misconception_description}" (ID: {misconception_id})\n\n'
        f"Original problem topic: {original_problem.topic}\n"
        f"Original problem:\n{original_problem.problem_text}\n\n"
        f"Generate {count} NEW Python predict_output problems to test whether the student has overcome this misconception.\n"
        "Requirements for each problem:\n"
        "- Must test the SAME underlying concept but use different surface code.\n"
        "- Must be short (3-8 lines), self-contained, valid Python 3 with no imports.\n"
        "- The correct output must differ from what a student with the misconception would predict.\n"
        "- Problems must be different from each other and from the original problem.\n\n"
        f"Respond with ONLY a JSON array of {count} objects, each with:\n"
        '  {"problem_text": "...", "correct_output": "...", "misconception_prediction": "..."}\n'
        "Order: easiest first."
    )
    content = _groq_chat(
        settings,
        [{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    if not content:
        return []
    # Try to extract a JSON array from the response
    try:
        # Sometimes the model wraps it in markdown
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        result = []
        for item in data[:count]:
            if "problem_text" in item and "correct_output" in item:
                result.append({
                    "problem_text": str(item["problem_text"]),
                    "correct_output": str(item["correct_output"]),
                    "topic": original_problem.topic,
                    "item_type": "predict_output",
                    "misconception_prediction": str(item.get("misconception_prediction", "")),
                })
        return result
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        log.error("Failed to parse retest generation response: %s", exc)
        return []
