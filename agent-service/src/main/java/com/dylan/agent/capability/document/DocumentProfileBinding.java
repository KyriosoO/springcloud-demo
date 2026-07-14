package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.shared.ref.AgentProfileRef;

/** trusted Profile/limit binding；package-private 构造器关闭 JSON/Provider 构造入口。 */
public final class DocumentProfileBinding {
    private final String invocationId;
    private final String requestCorrelationId;
    private final String registrationIdentity;
    private final AgentProfileRef agentProfileRef;
    private final String documentProfileVersion;
    private final ResourceLimitReference resourceLimitReference;
    private final String profileProjectionDigest;

    DocumentProfileBinding(
            String invocationId,
            String requestCorrelationId,
            String registrationIdentity,
            AgentProfileRef agentProfileRef,
            String documentProfileVersion,
            ResourceLimitReference resourceLimitReference,
            String profileProjectionDigest) {
        if (blank(invocationId) || blank(requestCorrelationId) || blank(registrationIdentity)
                || agentProfileRef == null || agentProfileRef.expectedVersion().isEmpty()
                || documentProfileVersion == null || !documentProfileVersion.matches("dp1-[0-9a-f]{64}")
                || resourceLimitReference == null
                || profileProjectionDigest == null || !profileProjectionDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("document profile binding incomplete");
        }
        this.invocationId = invocationId;
        this.requestCorrelationId = requestCorrelationId;
        this.registrationIdentity = registrationIdentity;
        this.agentProfileRef = agentProfileRef;
        this.documentProfileVersion = documentProfileVersion;
        this.resourceLimitReference = resourceLimitReference;
        this.profileProjectionDigest = profileProjectionDigest;
    }

    public String invocationId() { return invocationId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public String registrationIdentity() { return registrationIdentity; }
    public AgentProfileRef agentProfileRef() { return agentProfileRef; }
    public String documentProfileVersion() { return documentProfileVersion; }
    public ResourceLimitReference resourceLimitReference() { return resourceLimitReference; }
    public String profileProjectionDigest() { return profileProjectionDigest; }
    private static boolean blank(String value) { return value == null || value.isBlank(); }
}
