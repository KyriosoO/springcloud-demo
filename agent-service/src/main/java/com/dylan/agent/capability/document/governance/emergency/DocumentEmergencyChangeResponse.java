package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;

public record DocumentEmergencyChangeResponse(
        String changeId,DocumentEmergencyTargetType targetType,String targetKeyDigest,
        DocumentEmergencyControlState state,long rowVersion,
        DocumentEmergencyPropagationStatus propagationStatus,Instant updatedAt) {}
