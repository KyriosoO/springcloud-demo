package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.AgentAggregateMetricParameter;
import com.dylan.agent.api.response.AgentAggregateOrderParameter;
import com.dylan.agent.api.response.AgentAggregateParameters;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
import com.dylan.agent.api.response.AgentQueryFilterParameter;
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

class AggregateResultSecurityProjectorTest {

    @Test
    void supportsAggregateResultContract() {
        AggregateResultSecurityProjector projector = new AggregateResultSecurityProjector(maskingSupport());

        assertThat(projector.supports()).isEqualTo(AgentExecutionContracts.AGGREGATE_RESULT);
        assertThat(projector.payloadType()).isEqualTo(AggregateAgentResultPayload.class);
    }

    @Test
    void masksAggregateGroupValuesOnly() {
        AggregateResultSecurityProjector projector = new AggregateResultSecurityProjector(maskingSupport());

        FilteredResult<AggregateAgentResultPayload> filtered = projector.filter(payload(), scope());

        AgentAggregateResult result = filtered.payload().getAggregateResult();
        AgentAggregateParameters parameters = filtered.payload().getAggregateParameters();
        assertThat(parameters.getGroupByFields()).containsExactly("phoneNo");
        assertThat(parameters.getFilters())
                .singleElement()
                .satisfies(filter -> {
                    assertThat(filter.getField()).isEqualTo("phoneNo");
                    assertThat(filter.getValue()).isEqualTo("138****5678");
                });
        assertThat(parameters.getMetrics())
                .extracting(AgentAggregateMetricParameter::getAlias)
                .containsExactly("rowCount");
        assertThat(parameters.getOrderBy())
                .extracting(AgentAggregateOrderParameter::getField)
                .containsExactly("rowCount");
        assertThat(result.getGroupByFields()).containsExactly("phoneNo");
        assertThat(result.getRows().get(0).getGroups())
                .containsExactly(Map.entry("phoneNo", "138****5678"));
        assertThat(result.getMetricAliases()).containsExactly("totalAmount");
        assertThat(result.getRows().get(0).getMetrics())
                .containsExactly(Map.entry("totalAmount", 99));
    }

    @Test
    void filtersUnauthorizedGroupFields() {
        AggregateResultSecurityProjector projector = new AggregateResultSecurityProjector(maskingSupport());

        FilteredResult<AggregateAgentResultPayload> filtered = projector.filter(payload(), scope());

        assertThat(filtered.payload().getAggregateResult().getRows().get(0).getGroups())
                .doesNotContainKey("idCardNo");
    }

    @Test
    void failsClosedWhenFieldBearingPayloadHasNoDomain() {
        AggregateResultSecurityProjector projector = new AggregateResultSecurityProjector(maskingSupport());
        AggregateAgentResultPayload payload = payload();
        payload.getAggregateParameters().setDomain(null);
        payload.getAggregateResult().setDomain(null);

        assertThatThrownBy(() -> projector.filter(payload, scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing domain");
    }

    private AggregateAgentResultPayload payload() {
        AgentAggregateRow row = new AgentAggregateRow();
        row.setGroups(Map.of(
                "phoneNo", "13812345678",
                "idCardNo", "110101199001010011"));
        row.setMetrics(Map.of("totalAmount", 99));

        AgentAggregateResult result = new AgentAggregateResult();
        result.setDomain("employee");
        result.setGroupByFields(List.of("phoneNo", "idCardNo"));
        result.setMetricAliases(List.of("totalAmount"));
        result.setRows(List.of(row));
        result.setPartial(false);
        return new AggregateAgentResultPayload(parameters(), result);
    }

    private AgentAggregateParameters parameters() {
        AgentQueryFilterParameter allowedFilter = new AgentQueryFilterParameter();
        allowedFilter.setField("phoneNo");
        allowedFilter.setOperator(AgentOperator.EQ);
        allowedFilter.setValue("13812345678");

        AgentQueryFilterParameter deniedFilter = new AgentQueryFilterParameter();
        deniedFilter.setField("idCardNo");
        deniedFilter.setOperator(AgentOperator.EQ);
        deniedFilter.setValue("110101199001010011");

        AgentAggregateMetricParameter rowCount = new AgentAggregateMetricParameter();
        rowCount.setAlias("rowCount");
        rowCount.setFunction(AggregateFunction.COUNT);

        AgentAggregateMetricParameter deniedMetric = new AgentAggregateMetricParameter();
        deniedMetric.setAlias("idCardMax");
        deniedMetric.setFunction(AggregateFunction.MAX);
        deniedMetric.setField("idCardNo");

        AgentAggregateOrderParameter rowCountOrder = new AgentAggregateOrderParameter();
        rowCountOrder.setField("rowCount");
        rowCountOrder.setDirection("DESC");

        AgentAggregateOrderParameter deniedOrder = new AgentAggregateOrderParameter();
        deniedOrder.setField("idCardMax");
        deniedOrder.setDirection("DESC");

        AgentAggregateParameters parameters = new AgentAggregateParameters();
        parameters.setDomain("employee");
        parameters.setFilters(List.of(allowedFilter, deniedFilter));
        parameters.setMetrics(List.of(rowCount, deniedMetric));
        parameters.setGroupByFields(List.of("phoneNo", "idCardNo"));
        parameters.setOrderBy(List.of(rowCountOrder, deniedOrder));
        parameters.setMaxRows(20);
        return parameters;
    }

    private ExecutionScope scope() {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("aggregate.compute"),
                Set.of("employee"),
                Map.of("employee", Set.of("phoneNo")),
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
