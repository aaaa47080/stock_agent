from core.agents.analysis_policy import AnalysisPolicyResolver


def test_analysis_policy_builds_price_lookup_from_config():
    resolver = AnalysisPolicyResolver()

    profile = resolver.build_query_profile("AAPL 現在多少？", ["AAPL"])

    assert profile["query_type"] == "price_lookup"
    assert profile["has_symbol_candidates"] is True


def test_analysis_policy_resolves_verified_discovery_rule_from_config():
    resolver = AnalysisPolicyResolver()

    decision = resolver.resolve({
        "analysis_mode": "verified",
        "metadata": {
            "market_resolution": {
                "requires_discovery_lookup": True,
            },
            "query_profile": {
                "query_type": "price_lookup",
            },
        },
    })

    assert decision.required_tool_role == "discovery_lookup"
    assert decision.fail_reason == "verified_discovery_tool_unavailable"


def test_analysis_policy_resolves_research_discovery_rule_from_config():
    resolver = AnalysisPolicyResolver()

    decision = resolver.resolve({
        "analysis_mode": "research",
        "metadata": {
            "market_resolution": {
                "requires_discovery_lookup": True,
            },
            "query_profile": {
                "query_type": "price_lookup",
            },
        },
    })

    assert decision.required_tool_role == "discovery_lookup"
    assert decision.fail_reason == "research_discovery_tool_unavailable"
