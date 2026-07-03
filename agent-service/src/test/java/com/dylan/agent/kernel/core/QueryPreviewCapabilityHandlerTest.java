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

import java.time.Instant;
import java.util.List;
import java.util.Map;

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
        QueryableAdapter adapter = query -> {
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
        return new ExecutionContext(
                "inv-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                new AdapterExecutionBinding(
                        AdapterRole.QUERYABLE,
                        "employee",
                        QueryableAdapter.class,
                        adapter,
                        "adapter-v1",
                        Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:01:00Z"),
                new CancellationSource().token());
    }
}
