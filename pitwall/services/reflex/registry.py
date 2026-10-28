"""Rule registry — collects pure reflex-rule functions.

A reflex rule is a **pure function**: ``TelemetryFrame → AlertSpec | None``.
It performs no I/O, has no side effects, and is trivially unit-testable.
Adding a new rule is one small file plus one ``registry.register()`` call.
"""

from __future__ import annotations

from collections.abc import Callable

from pitwall.domain.models import AlertSpec, TelemetryFrame

# Canonical type for a reflex rule function.
ReflexRule = Callable[[TelemetryFrame], AlertSpec | None]


class RuleRegistry:
    """Thread-safe registry of named reflex rules.

    Usage::

        registry = RuleRegistry()

        @registry.rule("tire_deg")
        def check_tire_deg(frame: TelemetryFrame) -> AlertSpec | None:
            ...
    """

    def __init__(self) -> None:
        self._rules: dict[str, ReflexRule] = {}

    def register(self, name: str, rule: ReflexRule) -> None:
        """Register a rule function under ``name``.

        Raises:
            ValueError: If a rule with that name is already registered.
        """
        if name in self._rules:
            msg = f"Rule '{name}' is already registered"
            raise ValueError(msg)
        self._rules[name] = rule

    def rule(self, name: str) -> Callable[[ReflexRule], ReflexRule]:
        """Decorator form of :meth:`register`."""

        def decorator(fn: ReflexRule) -> ReflexRule:
            self.register(name, fn)
            return fn

        return decorator

    @property
    def rules(self) -> dict[str, ReflexRule]:
        """Snapshot of all registered rules (name → function)."""
        return dict(self._rules)

    def __len__(self) -> int:
        return len(self._rules)
