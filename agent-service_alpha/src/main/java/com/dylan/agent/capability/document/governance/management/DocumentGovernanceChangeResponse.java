package com.dylan.agent.capability.document.governance.management;
import java.time.Instant;
import java.util.Optional;
public record DocumentGovernanceChangeResponse(String changeId,DocumentRolloutUnitType unitType,String unitKeyDigest,
        DocumentGovernanceChangeStatus status,String expectedStateDigest,String targetStateDigest,
        Optional<String> currentStateDigest,Instant updatedAt) {public DocumentGovernanceChangeResponse{currentStateDigest=currentStateDigest==null?Optional.empty():currentStateDigest;}}
