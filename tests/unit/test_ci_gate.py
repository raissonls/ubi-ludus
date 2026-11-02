def test_ci_catches_failures() -> None:
    # Deliberately failing, to prove CI turns red. Reverted in the next commit.
    assert len("ubi") == 4
