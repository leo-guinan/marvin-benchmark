from marvin_benchmark.types import TaskInstance, ModelResponse, serialize_turn
from marvin_benchmark.evaluator import evaluate


def make_task(ref_turns):
    ref_stream = [serialize_turn(t, "client", i) for i, t in enumerate(ref_turns)]
    return TaskInstance(
        task_id="test-001", pillar=1, domain="test",
        visible_context={}, reference_stream=ref_stream,
        resistance_structure={}, activation_threshold=0.05
    )


def test_perfect_match_is_coherent():
    turns = ["hello", "I am struggling", "the real issue is fear"]
    task = make_task(turns)
    resp = ModelResponse(
        task_id="test-001",
        turns=[],
        actual_stream=[serialize_turn(t, "client", i) for i, t in enumerate(turns)]
    )
    result = evaluate(task, resp, "test-model")
    assert result.channel == "coherent"
    assert result.passed


def test_missing_turn_is_W_channel():
    turns = ["hello", "I am struggling", "the real issue is fear"]
    task = make_task(turns)
    # Drop middle turn
    partial = [turns[0], turns[2]]
    resp = ModelResponse(
        task_id="test-001", turns=[],
        actual_stream=[serialize_turn(t, "client", i) for i, t in enumerate(partial)]
    )
    result = evaluate(task, resp, "test-model")
    assert result.channel == "W"
    assert not result.passed
