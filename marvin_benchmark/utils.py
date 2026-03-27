"""Shared utilities."""
import json, re


def llm_json(model: str, messages: list[dict], **kwargs) -> dict | list:
    """
    Call an LLM and parse JSON from the response.
    Works with models that don't support response_format=json_object.
    Falls back to regex extraction if direct parse fails.
    Retries up to 3 times on empty responses (rate limit / throttle).
    """
    import litellm, time, random
    # Remove response_format if model doesn't support it
    kwargs.pop("response_format", None)
    # Ensure enough tokens for large JSON responses
    kwargs.setdefault("max_tokens", 3000)  # reasoning models burn tokens on internal thinking

    content = ""
    for attempt in range(5):
        if attempt > 0:
            wait = 2 ** attempt + random.uniform(0, 1)
            time.sleep(wait)
        try:
            resp = litellm.completion(model=model, messages=messages, **kwargs)
            content = resp.choices[0].message.content or ""
            finish = resp.choices[0].finish_reason
            if content.strip():
                break
            # If finish=length with empty content, reasoning used all tokens — bump budget
            if finish == "length" and not content.strip():
                kwargs["max_tokens"] = int(kwargs.get("max_tokens", 1500) * 1.5)
        except Exception as e:
            if attempt == 4:
                raise
            continue

    if not content.strip():
        raise ValueError(f"Model returned empty content after 5 attempts (finish={finish})")
    
    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON block from markdown
    for pattern in [r"```json\s*([\s\S]+?)\s*```", r"```\s*([\s\S]+?)\s*```"]:
        m = re.search(pattern, content)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    
    # Try finding the outermost { } or [ ]
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = content.find(start_char)
        end = content.rfind(end_char)
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end+1])
            except json.JSONDecodeError:
                pass
    
    raise ValueError(f"Could not parse JSON from response: {content[:200]}")
