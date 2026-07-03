package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.QueryPreviewResult;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

class QueryPreviewResultSecurityProjectorTest {

    @Test
    void supportsQueryPreviewResultContract() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector();

        assertThat(projector.supports()).isEqualTo(AgentExecutionContracts.QUERY_PREVIEW_RESULT);
        assertThat(projector.payloadType()).isEqualTo(QueryPreviewResultPayload.class);
    }

    @Test
    void filtersUnauthorizedFields() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector();

        FilteredResult<QueryPreviewResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.payload().getQueryParameters().getSelectFields())
                .containsExactly("chineseName");
        assertThat(filtered.payload().getPreviewResult().getColumns())
                .containsExactly("chineseName");
        assertThat(filtered.payload().getPreviewResult().getSampleRows())
                .containsExactly(Map.of("chineseName", "张三"));
    }

    @Test
    void createsSafeMessageAndSummary() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector();

        FilteredResult<QueryPreviewResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.safeMessage()).isEqualTo("查询预览完成");
        assertThat(filtered.safeSummary()).contains("过滤");
    }

    private QueryPreviewResultPayload payload() {
        AgentQueryFilterParameter filter = new AgentQueryFilterParameter();
        filter.setField("chineseName");

        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setFilters(List.of(filter));
        parameters.setSelectFields(List.of("chineseName", "idCardNo"));
        parameters.setPage(1);
        parameters.setSize(2);

        QueryPreviewResult result = new QueryPreviewResult();
        result.setColumns(List.of("chineseName", "idCardNo"));
        result.setSampleRows(List.of(Map.of("chineseName", "张三", "idCardNo", "110101199001010011")));
        result.setTotalEstimate(1L);
        result.setTotalExact(true);
        result.setPreviewSize(2);
        return new QueryPreviewResultPayload(parameters, result);
    }

    private ExecutionScope scope() {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.preview"),
                Set.of("employee"),
                Map.of("employee", Set.of("chineseName")),
                Map.of(),
                Duration.ofSeconds(30),
                0,
                100,
                10_000);
    }
}
