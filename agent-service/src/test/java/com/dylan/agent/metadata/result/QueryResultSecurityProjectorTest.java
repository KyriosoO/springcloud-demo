package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
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

class QueryResultSecurityProjectorTest {

    @Test
    void supportsQueryResultContract() {
        QueryResultSecurityProjector projector = new QueryResultSecurityProjector(maskingSupport());

        assertThat(projector.supports()).isEqualTo(AgentExecutionContracts.QUERY_RESULT);
        assertThat(projector.payloadType()).isEqualTo(QueryAgentResultPayload.class);
    }

    @Test
    void filtersAndMasksQueryRows() {
        QueryResultSecurityProjector projector = new QueryResultSecurityProjector(maskingSupport());

        FilteredResult<QueryAgentResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.payload().getQueryResult().getColumns())
                .containsExactly("chineseName", "phoneNo");
        assertThat(filtered.payload().getQueryResult().getRows())
                .containsExactly(Map.of(
                        "chineseName", "张三",
                        "phoneNo", "138****5678"));
    }

    @Test
    void masksQueryFilterValues() {
        QueryResultSecurityProjector projector = new QueryResultSecurityProjector(maskingSupport());

        FilteredResult<QueryAgentResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.payload().getQueryParameters().getFilters())
                .extracting(AgentQueryFilterParameter::getValue)
                .containsExactly("138****5678");
    }

    @Test
    void failsClosedWhenFieldBearingPayloadHasNoDomain() {
        QueryResultSecurityProjector projector = new QueryResultSecurityProjector(maskingSupport());
        QueryAgentResultPayload payload = payload();
        payload.getQueryParameters().setDomain(null);

        assertThatThrownBy(() -> projector.filter(payload, scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing domain");
    }

    private QueryAgentResultPayload payload() {
        AgentQueryFilterParameter phoneFilter = new AgentQueryFilterParameter();
        phoneFilter.setField("phoneNo");
        phoneFilter.setOperator(AgentOperator.EQ);
        phoneFilter.setValue("13812345678");
        AgentQueryFilterParameter idCardFilter = new AgentQueryFilterParameter();
        idCardFilter.setField("idCardNo");
        idCardFilter.setOperator(AgentOperator.EQ);
        idCardFilter.setValue("110101199001010011");

        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setFilters(List.of(phoneFilter, idCardFilter));
        parameters.setSelectFields(List.of("chineseName", "phoneNo", "idCardNo"));
        parameters.setPage(1);
        parameters.setSize(2);

        AgentQueryResult result = new AgentQueryResult();
        result.setColumns(List.of("chineseName", "phoneNo", "idCardNo"));
        result.setRows(List.of(Map.of(
                "chineseName", "张三",
                "phoneNo", "13812345678",
                "idCardNo", "110101199001010011")));
        result.setTotal(1L);
        result.setTotalExact(true);
        result.setPage(1);
        result.setSize(2);
        return new QueryAgentResultPayload(parameters, result);
    }

    private ExecutionScope scope() {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of("employee", Set.of("chineseName", "phoneNo")),
                Map.of("employee.phoneNo", MaskType.MOBILE),
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
