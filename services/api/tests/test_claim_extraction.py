"""L-2/L-4: deterministic claim extraction, including clause-level polarity."""

from app.services.claim_extraction import extract_claims


def _by_object(claims):
    return {(c.object_literal, c.polarity) for c in claims if c.predicate == "works_in"}


def test_clause_split_gives_each_condition_its_own_polarity() -> None:
    claims = extract_claims(
        subject_label="ORB",
        strategy_info=None,
        text="It works well in a trending market but should be avoided in chop.",
    )
    pairs = _by_object(claims)
    # "trend" is supported; only "chop" is refuted — the negation must not leak.
    assert ("trend", "supports") in pairs
    assert ("chop", "refutes") in pairs
    assert ("trend", "refutes") not in pairs


def test_structured_rules_become_claims() -> None:
    claims = extract_claims(
        subject_label="ORB",
        strategy_info={"entry_rules": ["break of the first 15m range"], "market": "futures"},
        text="",
    )
    predicates = {c.predicate for c in claims}
    assert "enters_when" in predicates
    assert "works_in" in predicates


def test_negation_marks_refutes() -> None:
    claims = extract_claims(
        subject_label="ORB", strategy_info=None, text="This never works in chop."
    )
    assert any(c.polarity == "refutes" and c.object_literal == "chop" for c in claims)
