package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;

import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** exact Policy version 对文档 Profile、channel 和 operation 的显式收窄。 */
public record DocumentPolicyConstraint(
        String policyVersion,
        Map<String, Set<String>> allowedProfileNamesByDomain,
        Map<String, Set<DocumentRetrievalChannel>> allowedChannelsByDomain,
        Map<String, Set<DocumentPlanOperation>> allowedOperationsByDomain,
        String evidenceDigest) {
    public DocumentPolicyConstraint {
        policyVersion = text(policyVersion, "policyVersion");
        allowedProfileNamesByDomain = immutable(allowedProfileNamesByDomain, "profile names");
        allowedChannelsByDomain = immutable(allowedChannelsByDomain, "channels");
        allowedOperationsByDomain = immutable(allowedOperationsByDomain, "operations");
        if (!allowedProfileNamesByDomain.keySet().equals(allowedChannelsByDomain.keySet())
                || !allowedProfileNamesByDomain.keySet().equals(allowedOperationsByDomain.keySet())) {
            throw new IllegalArgumentException("document policy domains must exactly align");
        }
        if (evidenceDigest == null || !evidenceDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid document policy evidence digest");
        }
    }

    public String evidenceRef() { return policyVersion + ":" + evidenceDigest; }

    private static <T> Map<String, Set<T>> immutable(Map<String, Set<T>> source, String name) {
        Objects.requireNonNull(source);
        var result = new java.util.LinkedHashMap<String, Set<T>>();
        source.forEach((domain, values) -> {
            String key = text(domain, "policy domain");
            Set<T> copy = Set.copyOf(Objects.requireNonNull(values));
            if (copy.isEmpty()) throw new IllegalArgumentException("document policy " + name + " must not be empty");
            result.put(key, copy);
        });
        if (result.isEmpty()) throw new IllegalArgumentException("document policy domains must not be empty");
        return Map.copyOf(result);
    }

    private static String text(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) throw new IllegalArgumentException(name + " must not be blank");
        return normalized;
    }
}
