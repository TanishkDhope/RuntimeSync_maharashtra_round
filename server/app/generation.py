import json
import urllib.request
import logging
from .config import Settings
from .data import Problem

log = logging.getLogger("relearn")

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
    
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "relearn/1.0"
        },
        data=json.dumps(payload).encode("utf-8")
    )
    
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return content
    except Exception as exc:
        log.error("Failed to generate misconception with Groq: %s", exc)
        # Fallback description if the API fails
        return f"Unknown misconception on {problem.topic}: {student_response[:20]}..."
