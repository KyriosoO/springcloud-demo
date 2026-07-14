package com.dylan.agent.testsupport;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.metadata.authorization.model.ExternalProcessingAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.ExternalProcessingFieldRule;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.SecurityClassificationRef;
import com.dylan.agent.model.MaskType;

import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/** P1 external-processing 证据的测试构建器。 */
public final class ExternalProcessingTestSupport {
    private ExternalProcessingTestSupport() {}

    public static ExternalProcessingAuthorizationEvidence denied() {
        return new ExternalProcessingAuthorizationEvidence(
                Map.of(), Map.of(), "1".repeat(64), "2".repeat(64));
    }

    public static ExternalProcessingAuthorizationEvidence allowed(
            String domain,
            Set<String> fields,
            Set<CapabilityOperationType> purposes) {
        SecurityClassificationRef classification =
                new SecurityClassificationRef("test", "internal", "v1");
        Map<CanonicalFieldRef, ExternalProcessingFieldRule> rules = fields.stream()
                .map(field -> new CanonicalFieldRef(domain, field))
                .collect(Collectors.toUnmodifiableMap(
                        field -> field,
                        field -> new ExternalProcessingFieldRule(
                                field, classification, MaskType.NONE, purposes)));
        Map<String, Set<CapabilityOperationType>> domains = Map.of(domain, purposes);
        String policyDigest = ExternalProcessingAuthorizationEvidence.policyDigest(
                "policy-v1", domains, rules);
        String permissionDigest = ExternalProcessingAuthorizationEvidence.permissionDigest(
                "perm-evidence", "perm-v1", domains.keySet(), rules.keySet());
        return new ExternalProcessingAuthorizationEvidence(
                domains, rules, policyDigest, permissionDigest);
    }
}
