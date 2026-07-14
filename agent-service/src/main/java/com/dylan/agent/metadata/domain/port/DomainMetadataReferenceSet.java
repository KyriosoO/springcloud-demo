package com.dylan.agent.metadata.domain.port;

import java.util.Objects;
import java.util.Set;

/**
 * 必须基于一个不可变 D04 catalog view 校验的 typed references。
 */
public record DomainMetadataReferenceSet(
        Set<String> domains,
        Set<CanonicalFieldRef> fields,
        Set<CanonicalOperatorRef> operators,
        Set<CanonicalFunctionRef> functions) {

    public DomainMetadataReferenceSet {
        domains = Set.copyOf(domains == null ? Set.of() : domains);
        fields = Set.copyOf(fields == null ? Set.of() : fields);
        operators = Set.copyOf(operators == null ? Set.of() : operators);
        functions = Set.copyOf(functions == null ? Set.of() : functions);
        for (String domain : domains) {
            if (domain == null || domain.isBlank()) {
                throw new IllegalArgumentException("domain reference must not be blank");
            }
        }
        for (CanonicalFieldRef field : fields) {
            if (!domains.contains(field.domain())) {
                throw new IllegalArgumentException("field domain must also appear in domains");
            }
        }
        for (CanonicalOperatorRef operator : operators) {
            if (!fields.contains(operator.fieldRef())) {
                throw new IllegalArgumentException(
                        "operator field must also appear in fields: " + operator.fieldRef());
            }
        }
        for (CanonicalFunctionRef function : functions) {
            if (!fields.contains(function.fieldRef())) {
                throw new IllegalArgumentException(
                        "function field must also appear in fields: " + function.fieldRef());
            }
        }
    }

    public static DomainMetadataReferenceSet empty() {
        return new DomainMetadataReferenceSet(Set.of(), Set.of(), Set.of(), Set.of());
    }

    public boolean isEmpty() {
        return domains.isEmpty() && fields.isEmpty() && operators.isEmpty() && functions.isEmpty();
    }
}
