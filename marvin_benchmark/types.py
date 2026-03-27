from dataclasses import dataclass, field
from typing import Literal
import hashlib

Pillar = Literal[1, 2, 3]
Channel = Literal["coherent", "W", "RGB"]

@dataclass
class TaskInstance:
    task_id: str
    pillar: Pillar
    domain: str
    visible_context: dict          # what the model sees
    reference_stream: list[bytes]  # hidden ground truth sequence
    resistance_structure: dict     # how hidden entity resists direct approach
    activation_threshold: float    # sigma below which = pass (default 0.05)
    metadata: dict = field(default_factory=dict)

@dataclass
class ModelResponse:
    task_id: str
    turns: list[dict]              # [{role, content, serialized: bytes}]
    actual_stream: list[bytes]

@dataclass
class EvalResult:
    task_id: str
    pillar: Pillar
    sigma: float
    channel: Channel
    divergence_turn: int | None    # first turn where divergence detected
    incidents: list[dict]          # [{type, src_idx, tgt_idx}]
    passed: bool
    model: str
    notes: str = ""

def serialize_turn(content: str, role: str, turn_idx: int) -> bytes:
    """Deterministic serialization of a conversation turn to bytes."""
    canonical = f"{turn_idx}:{role}:{content.strip().lower()}"
    return hashlib.sha256(canonical.encode()).digest()

def serialize_state(state: dict, turn_idx: int) -> bytes:
    """Deterministic serialization of a state dict to bytes."""
    import json
    canonical = f"{turn_idx}:" + json.dumps(state, sort_keys=True)
    return hashlib.sha256(canonical.encode()).digest()
