"""Tests for GraphConfig"""
import pytest
from core.agents_v2.config import (
    GraphConfig, AgentFeatureConfig, FeatureToggle, create_default_config
)


class TestAgentFeatureConfig:
    def test_default_enabled(self):
        cfg = AgentFeatureConfig(name="test")
        assert cfg.enabled is True
        assert cfg.should_run({}) is True

    def test_disabled(self):
        cfg = AgentFeatureConfig(name="test", enabled=False)
        assert cfg.should_run({}) is False

    def test_condition(self):
        cfg = AgentFeatureConfig(
            name="test",
            condition=lambda ctx: ctx.get("task_type") == "analysis"
        )
        assert cfg.should_run({"task_type": "analysis"}) is True
        assert cfg.should_run({"task_type": "simple_price"}) is False


class TestGraphConfig:
    def test_get_active_agents(self):
        config = GraphConfig()
        config.agents = {
            "a1": AgentFeatureConfig(name="a1", enabled=True),
            "a2": AgentFeatureConfig(name="a2", enabled=False),
            "a3": AgentFeatureConfig(name="a3", enabled=True),
        }
        active = config.get_active_agents()
        assert "a1" in active
        assert "a2" not in active
        assert "a3" in active

    def test_get_active_tools(self):
        config = GraphConfig()
        config.tools = {"rsi": True, "macd": False, "bb": True}
        active = config.get_active_tools()
        assert "rsi" in active
        assert "macd" not in active

    def test_enable_disable_agent(self):
        config = GraphConfig()
        config.agents["test"] = AgentFeatureConfig(name="test", enabled=True)

        config.disable_agent("test")
        assert config.agents["test"].enabled is False

        config.enable_agent("test")
        assert config.agents["test"].enabled is True

    def test_feature_toggle(self):
        config = GraphConfig()
        config.features["debate"] = FeatureToggle.ON
        assert config.is_feature_enabled("debate") is True

        config.set_feature("debate", FeatureToggle.OFF)
        assert config.is_feature_enabled("debate") is False


class TestCreateDefaultConfig:
    def test_creates_config(self):
        config = create_default_config()
        assert "technical_analysis" in config.agents
        assert "sentiment_analysis" in config.agents
        assert len(config.tools) > 0

    def test_technical_analysis_condition(self):
        config = create_default_config()
        cfg = config.agents["technical_analysis"]

        assert cfg.should_run({"task_type": "analysis"}) is True
        assert cfg.should_run({"task_type": "simple_price"}) is False
