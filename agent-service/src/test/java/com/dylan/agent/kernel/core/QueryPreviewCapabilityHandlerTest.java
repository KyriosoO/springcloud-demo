package com.dylan.agent.kernel.core;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.capability.querypreview.QueryPreviewCapabilityHandler;
import com.dylan.agent.capability.querypreview.QueryPreviewPlanValidator;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

class QueryPreviewCapabilityHandlerTest {

    @Test
    void executesAdapterQueryAndBuildsPreviewPayloadWithoutContextWrite() {
        QueryPreviewCapabilityHandler handler = new QueryPreviewCapabilityHandler();
        ValidatedQuery query = new ValidatedQuery(
                List.of(new ValidatedFilter("name", AgentOperator.EQ, "Alice", List.of())),
                List.of("name"),
                1,
                2);

        var result = handler.execute(
                new com.dylan.agent.capability.querypreview.ValidatedQueryPreviewPlan(
                        QueryPreviewPlanValidator.KERNEL_CAPABILITY_ID,
                        "employee",
                        query,
                        List.of("name"),
                        2),
                context(query));

        assertThat(result.output().getResultKind().name()).isEqualTo("QUERY_PREVIEW");
        assertThat(result.output().getQueryParameters().getDomain()).isEqualTo("employee");
        assertThat(result.output().getPreviewResult().getColumns()).containsExactly("name");
        assertThat(result.output().getPreviewResult().getSampleRows())
                .containsExactly(Map.of("name", "Alice"), Map.of("name", "Bob"));
        assertThat(result.contextWrites()).isEmpty();
    }

    private ExecutionContext context(ValidatedQuery expectedQuery) {
        QueryableAdapter adapter = (query, operationContext) -> {
            assertThat(query).isSameAs(expectedQuery);
            return new AdapterQueryResult(
                    List.of(
                            Map.of("name", "Alice", "email", "alice@example.com"),
                            Map.of("name", "Bob", "email", "bob@example.com"),
                            Map.of("name", "Carol", "email", "carol@example.com")),
                    3,
                    true,
                    1,
                    2);
        };
        ExecutionScope scope = executionScope();
        return new ExecutionContext(
                "inv-1",
                "corr-1",
                "query.preview",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                scope,
                com.dylan.agent.testsupport.DomainMetadataTestSupport.binding(
                        AdapterRole.QUERYABLE,
                        "employee",
                        QueryableAdapter.class,
                        adapter,
                        "adapter-v1",
                        scope.domainMetadataEvidence(),
                        Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:01:00Z"),
                new CancellationSource().token());
    }

    private ExecutionScope executionScope() {
        Instant now = Instant.parse("2026-07-02T00:00:00Z");
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability", now),
                now,
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.preview"),
                Set.of("employee"),
                Map.of("employee", Set.of("name", "email")),
                Map.of(),
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective(20, 20, 1024 * 1024));
    }
}
