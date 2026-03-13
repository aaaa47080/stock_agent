---
name: stock-agent-platform
description: Use when working on this stock_agent platform's agent architecture, especially analysis_mode, verified-response policy, stock research workflows, finance eval coverage, tool gating by membership tier, or integrating skill-like rules into runtime behavior.
---

# Stock Agent Platform

Use this skill when the task is about integrating finance-oriented rules into the current platform without turning them into fake runtime tools.

## What this skill is for

- Converting "skills" into runtime policy, routing, and eval behavior
- Designing or implementing `analysis_mode` such as `quick`, `verified`, or later `research`
- Enforcing source/date/tool-use rules for finance answers
- Keeping membership-tier tool gating aligned with agent behavior
- Adding evaluation coverage for financial agent behavior

## Core rule

Do not model a skill as a frontend tool.

Use this layering instead:

- Policy layer: rule set and workflow constraints
- Runtime layer: manager routing, agent hooks, response constraints
- Tool layer: actual market/news/fundamental lookup tools

## Repo mapping

Inspect these files first:

- `/Users/a1031737/agent_stock/stock_agent/api/routers/analysis.py`
- `/Users/a1031737/agent_stock/stock_agent/core/agents/manager.py`
- `/Users/a1031737/agent_stock/stock_agent/core/agents/base_react_agent.py`
- `/Users/a1031737/agent_stock/stock_agent/core/agents/tool_registry.py`
- `/Users/a1031737/agent_stock/stock_agent/core/database/tools.py`
- `/Users/a1031737/agent_stock/stock_agent/docs/agent-skill-integration-plan.md`

## Skill-to-platform mapping

### signal-verification

Map to `analysis_mode=verified`.

Responsibilities:

- decide when tool use is required
- require date/source grounding for freshness-sensitive answers
- mark inference vs verified facts

### stock-research

Map to a later `analysis_mode=research`.

Responsibilities:

- orchestrate multi-step research
- combine price/news/fundamentals/filings
- do not force old bull/bear debate formatting

### agent-eval-finance

Map to tests and eval harness, not user-facing runtime.

Responsibilities:

- verify tool usage for live-data questions
- verify free vs premium behavior
- verify verified-mode output constraints

### cost-aware-market-analysis

Map to manager routing and escalation policy.

Responsibilities:

- quick mode for simple questions
- verified mode for freshness-sensitive questions
- research mode only when depth is explicitly requested

## Recommended runtime modes

- `quick`
  - default
  - standard ReAct flow

- `verified`
  - force or strongly prefer tool usage for live questions
  - include date and source/tool mention
  - distinguish inference from observed data

- `research`
  - later phase
  - multi-step research workflow
  - only when explicitly requested

## Implementation workflow

1. Extend request model with `analysis_mode`
2. Propagate mode into manager state and subtask context
3. Add verified-policy hooks in `BaseReActAgent`
4. Enforce tool-required path for freshness-sensitive finance questions
5. Add response constraints for verified mode
6. Add eval tests for tool use and output structure

## Constraints

- Do not reintroduce old bull/bear default response templates
- Do not create a monolithic "skill tool"
- Do not let verified mode silently answer freshness-sensitive finance questions without checking available tools first
- Prefer using existing `ToolMetadata.required_tier` and `get_allowed_tools()` instead of duplicating access logic

## Expected output when using this skill

When proposing or implementing changes, keep outputs anchored to:

- where the policy lives
- where tool enforcement happens
- how membership gating interacts with it
- what tests prove the behavior
