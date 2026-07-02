package com.dylan.agent.metadata.context.migration;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/** Exact source/target migration registry; no latest or path search. */
public final class ContextMigrationRegistry {

    private final List<ContextPayloadMigrator<?, ?>> migrators;

    public ContextMigrationRegistry(List<ContextPayloadMigrator<?, ?>> migrators) {
        this.migrators = List.copyOf(migrators == null ? List.of() : migrators);
        validateNoAmbiguousPathOrCycle();
    }

    public Optional<ContextPayloadMigrator<?, ?>> resolve(ContractRef source, ContractRef target) {
        Objects.requireNonNull(source, "source must not be null");
        Objects.requireNonNull(target, "target must not be null");
        return migrators.stream()
                .filter(migrator -> migrator.source().equals(source) && migrator.target().equals(target))
                .findFirst();
    }

    public void validateNoAmbiguousPathOrCycle() {
        java.util.Set<String> edges = new java.util.HashSet<>();
        for (ContextPayloadMigrator<?, ?> migrator : migrators) {
            String key = migrator.source() + "->" + migrator.target();
            if (!edges.add(key)) {
                throw new IllegalStateException("ambiguous context migration: " + key);
            }
            if (migrator.source().equals(migrator.target())) {
                throw new IllegalStateException("context migration cycle: " + key);
            }
        }
    }
}
