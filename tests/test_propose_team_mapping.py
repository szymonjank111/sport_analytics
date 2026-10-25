import pytest

from propose_team_mapping import canonical_name, slug


@pytest.mark.parametrize(
    ("source_name", "name", "team_id"),
    [
        ("Manchester United FC", "Manchester United", "manchester-united"),
        ("AFC Bournemouth", "Bournemouth", "bournemouth"),
        ("Brighton & Hove Albion FC", "Brighton & Hove Albion", "brighton-hove-albion"),
        ("Śląsk Wrocław", "Śląsk Wrocław", "slask-wroclaw"),
        ("Atlético de Madrid", "Atlético de Madrid", "atletico-de-madrid"),
    ],
)
def test_proposes_a_name_and_a_slug(source_name: str, name: str, team_id: str) -> None:
    assert canonical_name(source_name) == name
    assert slug(name) == team_id
