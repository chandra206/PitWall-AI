# ADR-004: JSON-in-Content Approach for Reasoning Models

**Status:** Accepted
**Date:** 2025-06-15
**Deciders:** PitWall AI Team

## Context

The Ultra strategist uses a **reasoning model** (e.g. DeepSeek-R1) that
produces long chain-of-thought responses.  These models often resist
strict structured-output schemas (function calling, JSON mode) because
their reasoning process needs free-form text.

## Decision

Use the **JSON-in-content** prompting pattern:

1. Prompt the model to "reason step by step" in natural language.
2. Ask it to embed a JSON block (`\`\`\`json ... \`\`\``) with the
   structured strategy output inside its response.
3. Parse the response by extracting the first JSON object, handling:
   - Fenced code blocks (`\`\`\`json ... \`\`\``)
   - Raw `{ ... }` blocks
   - Nested braces via depth tracking.

The parser (`UltraStrategistService._extract_json_block`) is robust to
surrounding text and falls back to a canned strategy if extraction fails.

## Consequences

**Positive:**
- Works with reasoning models that perform poorly in strict JSON mode.
- Preserves the model's chain-of-thought reasoning for logging/auditing.
- The structured output is still typed and validated via Pydantic.

**Negative:**
- Parsing is heuristic — edge cases with nested JSON strings are possible.
- Slightly higher token usage (reasoning + JSON vs. JSON alone).
- Parse failures require a fallback strategy.

## Mitigation

Parse failures trigger:
1. A `nano.parse_errors` / `ultra.parse_errors` metric increment.
2. A warning-level log with the raw response snippet.
3. A canned fallback strategy based on the original rule name.

This ensures the driver always gets actionable guidance, even when the
model output is malformed.
