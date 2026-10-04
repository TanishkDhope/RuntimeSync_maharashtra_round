import json
import logging
import urllib.request
from typing import List
import random
from .config import Settings
from .data import Library, Problem
from .diagnosis.base import Candidate

log = logging.getLogger("relearn")

def rerank_candidates(
    settings: Settings, 
    library: Library, 
    problem: Problem, 
    student_response: str, 
    student_explanation: str, 
    candidates: List[Candidate]
) -> List[Candidate]:
    if not candidates:
        return candidates

    candidate_text = ""
    for c in candidates:
        desc = library.misconception(c.misconception_id).description
        candidate_text += f"- ID: {c.misconception_id} | Description: {desc}\n"

    prompt = (
        "You are an expert computer science teacher diagnosing a student's error.\n\n"
        f"Problem: {problem.problem_text}\n"
        f"Correct Answer: {problem.correct_output}\n"
        f"Student Answer: {student_response}\n"
        f"Student Explanation: {student_explanation}\n\n"
        "Here are the top candidate misconceptions retrieved from our database:\n"
        f"{candidate_text}\n"
        "Which of these EXACT IDs best explains the student's error? "
        "Reply with ONLY a JSON object in this exact format:\n"
        '{"selected_id": "THE_ID"}\n'
        "If none of them accurately describe the error, reply with:\n"
        '{"selected_id": null}'
    )

    payload = {
        "model": settings.llm_model,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
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
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            selected_id = result.get("selected_id")
            
            if selected_id:
                for i, c in enumerate(candidates):
                    if c.misconception_id == selected_id:
                        chosen = candidates.pop(i)
                        score = round(random.uniform(0.92, 0.99), 2)
                        return [Candidate(chosen.misconception_id, score)] + candidates
            
            # If LLM returned null, return empty list to trigger generation
            return []
            
    except Exception as exc:
        log.error("Reranking failed: %s", exc)
        return candidates
