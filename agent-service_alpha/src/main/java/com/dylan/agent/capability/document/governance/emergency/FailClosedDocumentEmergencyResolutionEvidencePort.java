package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;

public final class FailClosedDocumentEmergencyResolutionEvidencePort implements DocumentEmergencyResolutionEvidencePort {
    @Override public String requireCurrentEvidence(String resolutionEvidenceId,DocumentEmergencyGateTargetBinding target,Instant deadline){
        throw new SecurityException("document emergency resolution evidence adapter is unavailable");
    }
}
