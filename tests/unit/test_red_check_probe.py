def test_this_must_turn_ci_red() -> None:
    # Deliberately failing, to prove a red check blocks the merge. Never merged.
    assert len("ubi") == 4
