"""Frozen private measurement plan; no environment, network or authorization I/O."""

from __future__ import annotations

from dataclasses import dataclass
import json

from agent_runtime.model.contracts import ModelTaskId


@dataclass(frozen=True, slots=True)
class MeasurementPlan:
    case_count: int = 12
    tasks: tuple[tuple[ModelTaskId, str], ...] = (
        (ModelTaskId.ACTION_SELECTION, "action-selection-v5"),
        (ModelTaskId.KNOWLEDGE_REWRITE, "12"),
        (ModelTaskId.KNOWLEDGE_SUMMARY, "9"),
    )
    domains: tuple[str, ...] = ("tax.policy", "tax.law")
    paths: tuple[str, ...] = ("keyword", "vector")
    profile_reads_per_domain: int = 3
    identity_checks_per_case: int = 2
    identity_reads_per_check: int = 2
    live_health_reads: int = 18
    startup_health_reads: int = 40
    startup_binding_reads: int = 2

    def per_case(self) -> dict[str, int]:
        return {"model": len(self.tasks), "search": len(self.domains) * len(self.paths),
                "embedding": 1, "rerank": len(self.domains)}

    def limits(self) -> dict[str, int]:
        return {"cases": self.case_count,
                **{kind: self.case_count * count for kind, count in self.per_case().items()}}

    def launcher_limits(self) -> dict[str, int]:
        profile = len(self.domains) * self.profile_reads_per_domain
        return {
            "domainCount": len(self.domains),
            "profileReads": profile,
            "identityChecks": self.case_count * self.identity_checks_per_case,
            "identityReads": self.identity_reads_per_check,
            "liveHealthReads": self.live_health_reads,
            "liveBeforeCases": profile + self.live_health_reads,
            "runtimeMetadataEsHttpMax": (profile + self.live_health_reads + self.case_count
                                         * self.identity_checks_per_case * self.identity_reads_per_check),
            "startupHealthReads": self.startup_health_reads,
            "startupProxyMetadata": profile + self.startup_health_reads,
            "startupBindingReads": self.startup_binding_reads,
            "startupMetadataMax": profile + self.startup_health_reads + self.startup_binding_reads,
        }


PLAN = MeasurementPlan()


def main() -> None:
    print(json.dumps({"budgets": PLAN.limits(), "perCase": PLAN.per_case(),
                      **PLAN.launcher_limits()}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
