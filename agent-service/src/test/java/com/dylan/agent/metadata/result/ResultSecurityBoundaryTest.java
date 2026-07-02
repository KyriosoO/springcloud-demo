package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

class ResultSecurityBoundaryTest {

    @Test
    void serializesFilteredPayloadToCanonicalBytes() {
        ResultSecurityBoundary boundary = new ResultSecurityBoundary(
                ContractRegistry.from(List.of()),
                new ResultSecurityProjectorRegistry(List.of(new QueryResultSecurityProjector())),
                new PayloadJsonCodec());

        var secured = boundary.secure(
                new QueryAgentResultPayload(),
                AgentExecutionContracts.QUERY_RESULT,
                scope());

        assertThat(secured.outputContract()).isEqualTo(AgentExecutionContracts.QUERY_RESULT);
        assertThat(secured.canonicalPayload()).isNotEmpty();
        assertThat(secured.safeSummary()).contains("过滤");
    }

    @Test
    void missingProjectorFailsClosed() {
        ResultSecurityBoundary boundary = new ResultSecurityBoundary(
                ContractRegistry.from(List.of()),
                new ResultSecurityProjectorRegistry(List.of()),
                new PayloadJsonCodec());

        assertThatThrownBy(() -> boundary.secure(
                new QueryAgentResultPayload(),
                AgentExecutionContracts.QUERY_RESULT,
                scope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing ResultSecurityProjector");
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
                Map.of(),
                Map.of(),
                Duration.ofSeconds(30),
                0,
                100,
                10_000);
    }
}
