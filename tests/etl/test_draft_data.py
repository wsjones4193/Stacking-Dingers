"""
Tests for backend/etl/draft_data.py

Tests the CSV normalization logic that doesn't require a real database or CSV file.
"""

import io

import pandas as pd
import pytest

from backend.etl.draft_data import normalize_columns


class TestNormalizeColumns:
    def test_standard_columns_unchanged(self):
        df = pd.DataFrame(columns=["draft_id", "pick_number", "username", "round_number"])
        result = normalize_columns(df)
        assert "draft_id" in result.columns
        assert "pick_number" in result.columns

    def test_camel_case_renamed(self):
        df = pd.DataFrame(columns=["draftId", "pickNumber", "userName", "roundNumber"])
        result = normalize_columns(df)
        assert "draft_id" in result.columns
        assert "pick_number" in result.columns
        assert "username" in result.columns
        assert "round_number" in result.columns

    def test_unknown_columns_preserved(self):
        df = pd.DataFrame(columns=["draft_id", "mystery_column"])
        result = normalize_columns(df)
        assert "mystery_column" in result.columns

    def test_player_id_renamed_to_underdog_player_id(self):
        df = pd.DataFrame(columns=["player_id", "player_name"])
        result = normalize_columns(df)
        assert "underdog_player_id" in result.columns
