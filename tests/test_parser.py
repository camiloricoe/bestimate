"""Tests for Zillow __NEXT_DATA__ parser."""

import json
from pathlib import Path

from src.scraper.parser import (
    PropertyData,
    extract_next_data,
    parse_property,
    parse_search_results,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _wrap_in_html(next_data: dict) -> str:
    """Wrap __NEXT_DATA__ JSON in a minimal HTML page."""
    return (
        '<html><head></head><body>'
        f'<script id="__NEXT_DATA__" type="application/json">'
        f'{json.dumps(next_data)}'
        '</script></body></html>'
    )


class TestExtractNextData:
    def test_extracts_from_script_tag(self):
        data = {"props": {"pageProps": {}}}
        html = _wrap_in_html(data)
        result = extract_next_data(html)
        assert result == data

    def test_returns_none_for_missing_tag(self):
        html = "<html><body>No script here</body></html>"
        result = extract_next_data(html)
        assert result is None

    def test_returns_none_for_invalid_json(self):
        html = '<html><script id="__NEXT_DATA__" type="application/json">{invalid</script></html>'
        result = extract_next_data(html)
        assert result is None


class TestParseProperty:
    def test_parses_detail_page_fixture(self):
        with open(FIXTURES / "next_data_sample.json") as f:
            data = json.load(f)
        html = _wrap_in_html(data)
        result = parse_property(html)

        assert result is not None
        assert result.zpid == 61741482
        assert result.zestimate == 385000
        assert result.price == 399900
        assert result.beds == 3
        assert result.baths == 2.0
        assert result.sqft == 1850
        assert result.year_built == 1998
        assert result.property_type == "SINGLE_FAMILY"
        assert result.address == "1234 Oak Avenue"
        assert result.city == "Orlando"
        assert result.state == "FL"
        assert result.zip_code == "32801"

    def test_lot_size_acres_to_sqft(self):
        with open(FIXTURES / "next_data_sample.json") as f:
            data = json.load(f)
        html = _wrap_in_html(data)
        result = parse_property(html)

        assert result is not None
        # 0.25 acres = 10890 sqft
        assert result.lot_size_sqft is not None
        assert abs(result.lot_size_sqft - 10890) < 1

    def test_best_value_prefers_zestimate(self):
        with open(FIXTURES / "next_data_sample.json") as f:
            data = json.load(f)
        html = _wrap_in_html(data)
        result = parse_property(html)
        assert result is not None
        assert result.best_value == 385000

    def test_returns_none_for_no_property(self):
        html = _wrap_in_html({"props": {"pageProps": {}}})
        result = parse_property(html)
        assert result is None

    def test_to_dict(self):
        with open(FIXTURES / "next_data_sample.json") as f:
            data = json.load(f)
        html = _wrap_in_html(data)
        result = parse_property(html)
        assert result is not None
        d = result.to_dict()
        assert d["zpid"] == 61741482
        assert "raw_data" not in d


class TestParseSearchResults:
    def test_parses_search_results_fixture(self):
        with open(FIXTURES / "search_results_sample.json") as f:
            data = json.load(f)
        html = _wrap_in_html(data)
        results = parse_search_results(html)

        assert len(results) == 2
        assert results[0].zpid == 61741482
        assert results[0].zestimate == 385000
        assert results[0].beds == 3
        assert results[0].city == "Orlando"

        assert results[1].zpid == 61741999
        assert results[1].zestimate == 410000
        assert results[1].beds == 4

    def test_returns_empty_for_no_results(self):
        data = {"props": {"pageProps": {"searchPageState": {"cat1": {"searchResults": {"listResults": []}}}}}}
        html = _wrap_in_html(data)
        results = parse_search_results(html)
        assert results == []
