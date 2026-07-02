package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.metadata.context.migration.ContextMigrationRegistry;

class ContextMigrationRegistryTest {
    @Test
    void rejectsAmbiguousExactMigration() {
        var migrator = new TestMigrator();
        assertThatThrownBy(() -> new ContextMigrationRegistry(List.of(migrator, migrator)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ambiguous");
    }

    private static final class TestMigrator implements com.dylan.agent.metadata.context.migration.ContextPayloadMigrator<QueryCapabilityContextPayload, QueryCapabilityContextPayload> {
        public com.dylan.agent.api.contract.common.ContractRef source() { return AgentExecutionContracts.QUERY_CONTEXT; }
        public Class<QueryCapabilityContextPayload> sourceType() { return QueryCapabilityContextPayload.class; }
        public com.dylan.agent.api.contract.common.ContractRef target() { return new com.dylan.agent.api.contract.common.ContractRef("QueryCapabilityContextPayload", "2.0.0"); }
        public Class<QueryCapabilityContextPayload> targetType() { return QueryCapabilityContextPayload.class; }
        public QueryCapabilityContextPayload migrate(QueryCapabilityContextPayload sourcePayload) { return sourcePayload; }
    }
}
