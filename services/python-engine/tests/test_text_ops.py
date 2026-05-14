from __future__ import annotations

from app.text_ops import tokenize_text


def test_tokenize_text_adds_configured_ngrams_after_base_tokens():
    tokens, phrase_hits = tokenize_text(
        "rare earth recovery improves supply chain",
        {},
        {
            "use_phrase_lexicon": False,
            "preserve_domain_phrases": False,
            "enable_ngrams": True,
            "ngram_min": 2,
            "ngram_max": 3,
        },
    )

    assert phrase_hits == []
    assert tokens[:6] == ["rare", "earth", "recovery", "improves", "supply", "chain"]
    assert "rare_earth" in tokens
    assert "rare_earth_recovery" in tokens
    assert "supply_chain" in tokens
