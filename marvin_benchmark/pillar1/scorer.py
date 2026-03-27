"""
Secondary scoring for Pillar 1.
Closure gives sigma (trajectory quality).
This gives blocker_identified (0/1) — did the model name the real issue?
Combined score = sigma * 0.6 + blocker_identified * 0.4
"""
import litellm
import json


def score_blocker_identification(
    conversation: list[dict],
    true_hidden_blocker: str,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Extract coach's final hypothesis and check if it matches the true blocker.
    Returns {identified: bool, hypothesis: str, confidence: float}
    """
    # Find final hypothesis in conversation
    hypothesis = ""
    for msg in reversed(conversation):
        if msg["role"] == "assistant" and "I believe the real blocker is" in msg["content"]:
            hypothesis = msg["content"]
            break

    if not hypothesis:
        return {"identified": False, "hypothesis": "", "confidence": 0.0}

    # LLM judge
    prompt = f"""Does the coach's hypothesis correctly identify the real underlying issue?

True hidden blocker: {true_hidden_blocker}
Coach's hypothesis: {hypothesis}

Partial credit is allowed. Score 1.0 if the core issue is named, 0.5 if directionally correct, 0.0 if wrong.
Return JSON: {{"score": 0.0-1.0, "reasoning": "brief"}}"""

    from ..utils import llm_json
    data = llm_json(model, [{"role": "user", "content": prompt}])
    return {
        "identified": data["score"] >= 0.5,
        "hypothesis": hypothesis,
        "confidence": data["score"],
    }


def combined_score(sigma: float, blocker_score: float) -> float:
    """Sigma is inverted (lower = better). Blocker is direct (higher = better)."""
    sigma_score = max(0.0, 1.0 - sigma)  # invert: 0 sigma = 1.0, 1.0 sigma = 0.0
    return sigma_score * 0.6 + blocker_score * 0.4
