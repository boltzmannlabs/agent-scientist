"""Tests for the ranked fuzzy scorer used by the searchable curses pickers."""
from sci_cli.curses_ui import (
    _SearchState,
    _fuzzy_score,
    _handle_active_search_key,
)


class _FakeCurses:
    KEY_BACKSPACE = 263
    KEY_DOWN = 258
    KEY_ENTER = 343




def test_scorer_ranks_prefix_and_boundary_matches_higher():
    """Contiguous / word-boundary matches outrank scattered ones; non-subsequences never match."""
    assert _fuzzy_score("gpt-4o", "gpt") > _fuzzy_score("gpt-4o", "g4o")
    assert _fuzzy_score("claude-sonnet-4", "sonnet") > _fuzzy_score("claude-sonnet-4", "clad snnt")
    assert _fuzzy_score("gpt-4o", "zzz") is None


def test_esc_reaches_shared_cancel_instead_of_only_clearing_search():
    search = _SearchState(active=True, query="gpt")
    assert _handle_active_search_key(_FakeCurses, 27, search) == (False, False, False)
    assert search.query == "gpt"
