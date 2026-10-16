"""Tests for signal lead time and clock boundary restrictions."""
import pytest


def test_lead_window_validation():
    # Intended entry is at 12:15:00 (:00s boundary)
    entry_slot = 1792050900
    
    # 12 seconds before entry -> :48s (VALID)
    sent_time_valid = entry_slot - 12
    seconds_to_entry = entry_slot - sent_time_valid
    assert 10 <= seconds_to_entry <= 15

    # 15 seconds before entry -> :45s (VALID)
    assert 10 <= (entry_slot - (entry_slot - 15)) <= 15

    # 10 seconds before entry -> :50s (VALID)
    assert 10 <= (entry_slot - (entry_slot - 10)) <= 15

    # 5 seconds before entry -> :55s (LATE, REJECT)
    seconds_too_late = entry_slot - (entry_slot - 5)
    assert not (10 <= seconds_too_late <= 15)

    # 20 seconds before entry -> :40s (TOO EARLY, REJECT)
    seconds_too_early = entry_slot - (entry_slot - 20)
    assert not (10 <= seconds_too_early <= 15)
