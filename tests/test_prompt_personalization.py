from eval_prompt_personalization import cases, check


def test_synthetic_players_keep_their_memory():
    for case in cases():
        missing, forbidden = check(case)
        assert missing == [], (case["name"], missing)
        assert forbidden == [], (case["name"], forbidden)
