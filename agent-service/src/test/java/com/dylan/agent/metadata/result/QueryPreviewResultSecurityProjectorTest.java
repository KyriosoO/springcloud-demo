package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQuerySortParameter;
import com.dylan.agent.api.response.QueryPreviewResult;
import com.dylan.agent.api.response.QueryPreviewResultPayload;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

class QueryPreviewResultSecurityProjectorTest {

    @Test
    void supportsQueryPreviewResultContract() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector(maskingSupport());

        assertThat(projector.supports()).isEqualTo(AgentExecutionContracts.QUERY_PREVIEW_RESULT);
        assertThat(projector.payloadType()).isEqualTo(QueryPreviewResultPayload.class);
    }

    @Test
    void filtersUnauthorizedFields() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector(maskingSupport());

        FilteredResult<QueryPreviewResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.payload().getQueryParameters().getSelectFields())
                .containsExactly("chineseName");
        assertThat(filtered.payload().getPreviewResult().getColumns())
                .containsExactly("chineseName");
        assertThat(filtered.payload().getPreviewResult().getSampleRows())
                .containsExactly(Map.of("chineseName", "张三"));
        assertThat(filtered.payload().getQueryParameters().getSorts())
                .extracting(AgentQuerySortParameter::getField)
                .containsExactly("chineseName");
    }

    @Test
    void createsSafeMessageAndSummary() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector(maskingSupport());

        FilteredResult<QueryPreviewResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.safeMessage()).isEqualTo("查询预览完成");
        assertThat(filtered.safeSummary()).contains("过滤");
    }

    @Test
    void filtersAndMasksPreviewSampleRows() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector(maskingSupport());

        FilteredResult<QueryPreviewResultPayload> filtered = projector.filter(payload(), scopeWithIdCardMask());

        assertThat(filtered.payload().getPreviewResult().getSampleRows())
                .containsExactly(Map.of(
                        "chineseName", "张三",
                        "idCardNo", "110101********0011"));
    }

    @Test
    void reusesUnifiedMaskingSupportForFilterValues() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector(maskingSupport());

        FilteredResult<QueryPreviewResultPayload> filtered = projector.filter(payloadWithIdCardFilter(), scopeWithIdCardMask());

        assertThat(filtered.payload().getQueryParameters().getFilters())
                .extracting(AgentQueryFilterParameter::getValue)
                .containsExactly("110101********0011");
    }

    @Test
    void failsClosedWhenFieldBearingPayloadHasNoDomain() {
        QueryPreviewResultSecurityProjector projector = new QueryPreviewResultSecurityProjector(maskingSupport());
        QueryPreviewResultPayload payload = payload();
        payload.getQueryParameters().setDomain(null);

        assertThatThrownBy(() -> projector.filter(payload, scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing domain");
    }

    private QueryPreviewResultPayload payload() {
        AgentQueryFilterParameter filter = new AgentQueryFilterParameter();
        filter.setField("chineseName");

        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setFilters(List.of(filter));
        parameters.setSelectFields(List.of("chineseName", "idCardNo"));
        AgentQuerySortParameter nameSort = new AgentQuerySortParameter();
        nameSort.setField("chineseName");
        nameSort.setDirection("ASC");
        AgentQuerySortParameter idCardSort = new AgentQuerySortParameter();
        idCardSort.setField("idCardNo");
        idCardSort.setDirection("DESC");
        parameters.setSorts(List.of(nameSort, idCardSort));
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

    private QueryPreviewResultPayload payloadWithIdCardFilter() {
        AgentQueryFilterParameter filter = new AgentQueryFilterParameter();
        filter.setField("idCardNo");
        filter.setValue("110101199001010011");

        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setFilters(List.of(filter));
        parameters.setSelectFields(List.of("idCardNo"));
        parameters.setPage(1);
        parameters.setSize(2);

        QueryPreviewResult result = new QueryPreviewResult();
        result.setColumns(List.of("idCardNo"));
        result.setSampleRows(List.of(Map.of("idCardNo", "110101199001010011")));
        return new QueryPreviewResultPayload(parameters, result);
    }

    private ExecutionScope scopeWithIdCardMask() {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.preview"),
                Set.of("employee"),
                Map.of("employee", Set.of("chineseName", "idCardNo")),
                Map.of("employee.idCardNo", MaskType.ID_CARD),
                Duration.ofSeconds(30),
                0,
                100,
                10_000);
    }

    private ResultValueMaskingSupport maskingSupport() {
        return new ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker())));
    }
}
