package com.dylan.agent.metadata.authorization.port;

import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.request.CapabilityScopeSelection;
import com.dylan.agent.metadata.authorization.request.PlanningSecurityRequest;

public interface AuthorizationPlanningPort {
    PlanningAuthorizationEvidence capture(PlanningSecurityRequest request);
    void assertCurrent(PlanningAuthorizationEvidence evidence);
    AuthorizationSnapshot freezeCapabilityScope(
            PlanningAuthorizationEvidence evidence,
            CapabilityScopeSelection selection);
}
