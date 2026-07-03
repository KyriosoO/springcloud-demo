package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentAggregateRow;
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
        return new AggregateAgentResultPayload(result);
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
