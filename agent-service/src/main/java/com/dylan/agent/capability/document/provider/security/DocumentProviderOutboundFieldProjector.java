package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.result.ResultValueMaskingSupport;
import com.dylan.agent.model.MaskType;

import java.util.Objects;

/** 严格按 trusted outbound decision 对实际字段值执行唯一脱敏。 */
public final class DocumentProviderOutboundFieldProjector {
    private final ResultValueMaskingSupport masking;

    public DocumentProviderOutboundFieldProjector(ResultValueMaskingSupport masking) {
        this.masking = Objects.requireNonNull(masking, "masking must not be null");
    }

    public String stringValue(
            DocumentProviderOutboundPolicyDecision decision,
            ExecutionScope scope,
            String domain,
            String field,
            String value) {
        if (value == null) {
            return null;
        }
        assertMaskBinding(decision, scope, domain, field);
        Object masked = masking.maskValue(domain, field, value, scope);
        return Objects.toString(masked, null);
    }

    public Integer integerValue(
            DocumentProviderOutboundPolicyDecision decision,
            ExecutionScope scope,
            String domain,
            String field,
            Integer value) {
        if (value == null) {
            return null;
        }
        assertMaskBinding(decision, scope, domain, field);
        Object masked = masking.maskValue(domain, field, value, scope);
        if (!(masked instanceof Integer result)) {
            throw new IllegalArgumentException("masked provider integer field changed type");
        }
        return result;
    }

    private static void assertMaskBinding(
            DocumentProviderOutboundPolicyDecision decision,
            ExecutionScope scope,
            String domain,
            String field) {
        Objects.requireNonNull(scope, "scope must not be null");
        MaskType effective = scope.fieldMasks().getOrDefault(domain + "." + field, MaskType.NONE);
        if (rule(decision, domain, field).maskType() != effective) {
            throw new IllegalArgumentException("provider field mask binding mismatch");
        }
    }

    private static DocumentProviderFieldRuleDecision rule(
            DocumentProviderOutboundPolicyDecision decision,
            String domain,
            String field) {
        Objects.requireNonNull(decision, "decision must not be null");
        CanonicalFieldRef target = new CanonicalFieldRef(domain, field);
        return decision.orderedFieldRules().stream()
                .filter(candidate -> candidate.field().equals(target))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("provider field is absent from outbound decision"));
    }
}
