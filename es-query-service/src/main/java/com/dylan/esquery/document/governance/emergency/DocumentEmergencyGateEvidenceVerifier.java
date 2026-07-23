package com.dylan.esquery.document.governance.emergency;

import java.time.Instant;
import java.util.List;

public interface DocumentEmergencyGateEvidenceVerifier {
    DocumentEmergencyGateVerification verify(
            DocumentEmergencyGateEvidence evidence,
            DocumentEmergencyRolloutBinding expectedRollout,
            List<DocumentEmergencyGateTargetBinding> expectedTargets,
            Instant now);
}
