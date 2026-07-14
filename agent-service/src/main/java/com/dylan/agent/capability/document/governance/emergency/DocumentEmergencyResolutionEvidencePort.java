package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;

public interface DocumentEmergencyResolutionEvidencePort {
    String requireCurrentEvidence(
            String resolutionEvidenceId,DocumentEmergencyGateTargetBinding target,Instant deadline);
}
