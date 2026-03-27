import closure_sdk as closure
from .types import TaskInstance, ModelResponse, EvalResult, Channel


def evaluate(task: TaskInstance, response: ModelResponse, model: str) -> EvalResult:
    """
    Core evaluation. Compares response.actual_stream against task.reference_stream
    using Closure-SDK. Returns structured result.
    """
    ref = task.reference_stream
    act = response.actual_stream

    # Pad shorter stream with null bytes to same length for fair comparison
    max_len = max(len(ref), len(act)) if (ref or act) else 0
    ref_padded = ref + [b'\x00' * 32] * (max_len - len(ref))
    act_padded = act + [b'\x00' * 32] * (max_len - len(act))

    # Drift check via two Seers
    seer_ref = closure.Seer()
    seer_act = closure.Seer()
    for rb in ref_padded:
        seer_ref.ingest(rb)
    for ab in act_padded:
        seer_act.ingest(ab)
    cmp = seer_ref.compare(seer_act)
    sigma = cmp.drift

    # Full fault analysis via gilgamesh
    faults = closure.gilgamesh(ref_padded, act_padded)

    # Classify dominant channel
    if not faults:
        channel: Channel = "coherent"
    else:
        n_missing = sum(1 for f in faults if f.incident_type == "missing")
        n_reorder = sum(1 for f in faults if f.incident_type == "reorder")
        channel = "W" if n_missing >= n_reorder else "RGB"

    # First divergence turn
    divergence_turn = None
    if faults:
        first = faults[0]
        idx = first.source_index if first.source_index is not None else first.target_index
        divergence_turn = idx

    incidents = [
        {"type": f.incident_type, "src": f.source_index, "tgt": f.target_index}
        for f in faults[:20]
    ]

    return EvalResult(
        task_id=task.task_id,
        pillar=task.pillar,
        sigma=sigma,
        channel=channel,
        divergence_turn=divergence_turn,
        incidents=incidents,
        passed=sigma <= task.activation_threshold,
        model=model,
    )
