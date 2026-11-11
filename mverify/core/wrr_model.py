"""Executable reference model for the documented pcie_wrr_arbiter contract.

This model is intentionally state-oriented and structurally different from the
RTL's parallel-prefix implementation. It is useful for Python checks and is the
behavioral source used by the generated UVM checker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class WeightedRoundRobinModel:
    num_requesters: int
    weights: Sequence[int]
    pointer: int = 0
    remaining: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.num_requesters < 1:
            raise ValueError("num_requesters must be positive")
        if len(self.weights) != self.num_requesters:
            raise ValueError("one weight is required per requester")
        self.weights = tuple(int(x) for x in self.weights)
        if any(x < 0 for x in self.weights):
            raise ValueError("weights must be unsigned")
        if not self.remaining:
            self.remaining = [0] * self.num_requesters

    def reset(self) -> None:
        self.pointer = 0
        self.remaining = [0] * self.num_requesters

    def _weights(self, weights: Sequence[int] | None) -> tuple[int, ...]:
        values = self.weights if weights is None else tuple(int(x) for x in weights)
        if len(values) != self.num_requesters or any(x < 0 for x in values):
            raise ValueError("weights must be one unsigned value per requester")
        return tuple(values)

    def predict(self, request: Sequence[bool], weights: Sequence[int] | None = None) -> tuple[bool, int, int, bool]:
        if len(request) != self.num_requesters:
            raise ValueError("request width does not match requester count")
        weights = self._weights(weights)
        active = [bool(request[i]) and weights[i] > 0 for i in range(self.num_requesters)]
        eligible = [active[i] and self.remaining[i] > 0 for i in range(self.num_requesters)]
        reload = not any(eligible)
        candidates = active if reload else eligible
        grant = next((i for i in list(range(self.pointer, self.num_requesters)) + list(range(self.pointer)) if candidates[i]), -1)
        return (grant >= 0, max(grant, 0), (1 << grant) if grant >= 0 else 0, reload)

    def clock(self, request: Sequence[bool], accepted: bool, weights: Sequence[int] | None = None) -> tuple[bool, int, int]:
        weights = self._weights(weights)
        valid, index, onehot, reload = self.predict(request, weights)
        if valid and accepted:
            active = [bool(request[i]) and weights[i] > 0 for i in range(self.num_requesters)]
            if reload:
                self.remaining = [weights[i] if active[i] else 0 for i in range(self.num_requesters)]
            self.remaining[index] -= 1
            self.pointer = (index + 1) % self.num_requesters
        return valid, index, onehot
