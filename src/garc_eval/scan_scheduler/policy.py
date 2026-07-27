from __future__ import annotations

from garc_eval.scan_headroom.trusted_policies import (
    AnytimeLargestGapPolicy, MacroRegionLargestGapPolicy, PublicScanState,
    SequentialPolicy, TrustedPolicy, UniformPrefixPolicy,
)
from .config import SafeCoverageConfig


class SafeCoveragePolicy(TrustedPolicy):
    """Usable fallback selected after YOLO-guided value Gates failed.

    The caller must choose a frozen policy explicitly; there is no hidden
    per-video selector. The policy consumes only ``PublicScanState``.
    """

    def __init__(self, config: SafeCoverageConfig = SafeCoverageConfig()):
        self.config = config
        self.policy_id = config.policy_id
        if config.policy_id == "SEQUENTIAL": self._delegate = SequentialPolicy()
        elif config.policy_id == "UNIFORM_PREFIX": self._delegate = UniformPrefixPolicy()
        elif config.policy_id == "ANYTIME_LARGEST_GAP": self._delegate = AnytimeLargestGapPolicy()
        else: self._delegate = MacroRegionLargestGapPolicy(config.macro_region_size_units)

    def choose_next_unit(self, public_state: PublicScanState) -> str:
        return self._delegate.choose_next_unit(public_state)
