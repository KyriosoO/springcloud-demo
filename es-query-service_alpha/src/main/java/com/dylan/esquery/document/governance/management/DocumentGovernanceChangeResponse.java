package com.dylan.esquery.document.governance.management;

import java.time.Instant;
import java.util.Optional;

public record DocumentGovernanceChangeResponse(String changeId,DocumentRolloutUnitType unitType,String unitKeyDigest,
        DocumentGovernanceChangeStatus status,String expectedStateDigest,String targetStateDigest,
        Optional<String> currentStateDigest,Instant updatedAt) {}
