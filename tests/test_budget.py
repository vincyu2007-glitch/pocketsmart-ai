"""Budget allocation, formatting and shopping-link tests."""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from services.budget import (
    CATEGORY_WEIGHTS,
    allocate_budget,
    format_inr,
    normalise_weights,
    per_head,
    plan_summary,
    weights_for,
)
from services.shopping import (
    PLATFORMS,
    attach_product_links,
    build_search_url,
    is_safe_url,
    links_for_products,
    platform_key_for,
    platforms_for,
)


class TestAllocateBudget:
    @pytest.mark.parametrize("budget", [10000, 99999, 150000, 123457, 2500000])
    def test_parts_always_sum_to_the_total(self, budget):
        rows = allocate_budget(budget, CATEGORY_WEIGHTS["home"])
        assert sum(r["amount"] for r in rows) == budget

    def test_no_negative_or_zero_allocations(self):
        rows = allocate_budget(5000, CATEGORY_WEIGHTS["jewelry"])
        assert all(r["amount"] > 0 for r in rows)

    def test_rows_are_sorted_largest_first(self):
        rows = allocate_budget(200000, CATEGORY_WEIGHTS["party"])
        amounts = [r["amount"] for r in rows]
        assert amounts == sorted(amounts, reverse=True)

    def test_percentages_sum_approximately_to_100(self):
        rows = allocate_budget(250000, CATEGORY_WEIGHTS["party"])
        assert sum(r["percentage"] for r in rows) == pytest.approx(100, abs=1.0)

    def test_contingency_is_always_present(self):
        for plan in ("home", "party", "jewelry"):
            rows = allocate_budget(100000, CATEGORY_WEIGHTS[plan])
            assert any("contingen" in r["category"].lower() for r in rows)

    def test_rejects_zero_budget(self):
        with pytest.raises(ValueError):
            allocate_budget(0, CATEGORY_WEIGHTS["home"])

    def test_rejects_all_zero_weights(self):
        with pytest.raises(ValueError):
            allocate_budget(10000, {"a": 0, "b": 0})

    def test_weight_overrides_apply(self):
        weights = weights_for("party", {"Food & Beverages": 400})
        rows = allocate_budget(100000, weights)
        food = next(r for r in rows if r["category"] == "Food & Beverages")
        assert food["amount"] > 70000

    def test_unknown_override_is_ignored(self):
        weights = weights_for("party", {"Nonexistent Category": 500})
        assert "Nonexistent Category" not in weights

    def test_custom_weights_are_normalised(self):
        assert sum(normalise_weights({"a": 1, "b": 3}).values()) == pytest.approx(1.0)


class TestHelpers:
    def test_per_head_rounds(self):
        assert per_head(100000, 33) == 3030

    def test_per_head_handles_zero_guests(self):
        assert per_head(1000, 0) == 1000

    def test_plan_summary(self):
        rows = allocate_budget(100000, CATEGORY_WEIGHTS["home"])
        summary = plan_summary(100000, rows)
        assert summary["remaining"] == 0
        assert summary["contingency"] > 0

    @pytest.mark.parametrize(
        "value,expected",
        [(0, "0"), (999, "999"), (1500, "1,500"), (99999, "99,999"), (123456, "1.23 L")],
    )
    def test_format_inr(self, value, expected):
        assert format_inr(value) == expected


class TestShoppingLinks:
    def test_known_platform_url_is_https_and_hosted_correctly(self):
        url = build_search_url("amazon", "sofa 3 seater")
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "www.amazon.in"
        assert "sofa" in url

    def test_query_is_url_encoded(self):
        url = build_search_url("amazon", "3-seater sofa & table")
        assert "+" in url or "%26" in url
        assert " " not in url

    def test_slug_template_used_for_myntra(self):
        url = build_search_url("myntra", "gold earrings")
        assert url == "https://www.myntra.com/gold-earrings"

    def test_unknown_platform_falls_back_to_amazon(self):
        assert urlparse(build_search_url("nope", "lamp")).netloc == "www.amazon.in"

    def test_is_safe_url_rejects_http_and_lookalikes(self):
        assert is_safe_url("https://www.amazon.in/s?k=sofa")
        assert not is_safe_url("http://www.amazon.in/s?k=sofa")
        assert not is_safe_url("https://amazon.in.evil.com/s?k=sofa")
        assert not is_safe_url("javascript:alert(1)")

    def test_every_registered_platform_renders_a_safe_url(self):
        for key in PLATFORMS:
            assert is_safe_url(build_search_url(key, "test query")), key

    def test_platform_key_for_is_scoped_to_plan(self):
        assert platform_key_for("jewelry", "Myntra") == "myntra"
        # Swiggy is not a jewellery platform, so it must not resolve.
        assert platform_key_for("jewelry", "Swiggy") == "amazon"

    def test_platforms_for_returns_safe_metadata(self):
        rows = platforms_for("home")
        assert {r["key"] for r in rows} >= {"amazon", "ikea", "urbancompany"}
        assert all(set(r) == {"key", "name", "category", "note"} for r in rows)

    def test_links_for_products_deduplicates(self):
        products = [
            {"name": "Sofa", "platform": "IKEA", "search_terms": "sofa"},
            {"name": "Sofa again", "platform": "IKEA", "search_terms": "sofa"},
        ]
        links = links_for_products("home", products)
        assert len(links) == 1
        assert links[0]["platform"] == "IKEA"

    def test_links_respect_the_limit(self):
        products = [{"name": f"Item {i}", "platform": "Amazon", "search_terms": f"item {i}"} for i in range(30)]
        assert len(links_for_products("home", products, limit=5)) == 5

    def test_attach_product_links_writes_valid_urls(self):
        products = [{"name": "Sofa", "platform": "IKEA", "search_terms": "sofa"}]
        attach_product_links("home", products)
        assert is_safe_url(products[0]["search_url"])
        assert products[0]["search_platform"] == "IKEA"

    def test_attach_product_links_repairs_unknown_platforms(self):
        products = [{"name": "Sofa", "platform": "Some Unknown Shop", "search_terms": "sofa"}]
        attach_product_links("home", products)
        assert is_safe_url(products[0]["search_url"])
