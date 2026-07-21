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
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;

class ResultSecurityBoundaryTest {

    @Test
    void serializesFilteredPayloadToCanonicalBytes() {
        ResultSecurityBoundary boundary = new ResultSecurityBoundary(
                ContractRegistry.from(List.of()),
                new ResultSecurityProjectorRegistry(List.of(new QueryResultSecurityProjector(maskingSupport()))),
                new PayloadJsonCodec());

        var secured = boundary.secure(
                new QueryAgentResultPayload(),
                AgentExecutionContracts.QUERY_RESULT,
                scope(),
                scope().resourceLimits());

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
                scope(),
                scope().resourceLimits()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing ResultSecurityProjector");
    }

    @Test
    void doesNotReturnCandidateWhenMaskerFails() {
        ResultSecurityBoundary boundary = new ResultSecurityBoundary(
                ContractRegistry.from(List.of()),
                new ResultSecurityProjectorRegistry(List.of(new QueryResultSecurityProjector(
                        maskingSupportWithThrowingMobile()))),
                new PayloadJsonCodec());

        assertThatThrownBy(() -> boundary.secure(
                maskedPayload(),
                AgentExecutionContracts.QUERY_RESULT,
                scopeWithMask(),
                scopeWithMask().resourceLimits()))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("mask failed");
    }

    private ExecutionScope scope() {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of(),
                Map.of(),
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective(100, 100, 10_000));
    }

    private ExecutionScope scopeWithMask() {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of("employee", Set.of("phoneNo")),
                Map.of("employee.phoneNo", MaskType.MOBILE),
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective(100, 100, 10_000));
    }

    private QueryAgentResultPayload maskedPayload() {
        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setSelectFields(List.of("phoneNo"));
        AgentQueryResult result = new AgentQueryResult();
        result.setColumns(List.of("phoneNo"));
        result.setRows(List.of(Map.of("phoneNo", "13812345678")));
        return new QueryAgentResultPayload(parameters, result);
    }

    private ResultValueMaskingSupport maskingSupport() {
        return new ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new com.dylan.agent.mask.MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker())));
    }

    private ResultValueMaskingSupport maskingSupportWithThrowingMobile() {
        return new ResultValueMaskingSupport(new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new FieldMasker() {
                    @Override
                    public MaskType type() {
                        return MaskType.MOBILE;
                    }

                    @Override
                    public Object mask(Object value) {
                        throw new IllegalStateException("mask failed");
                    }
                },
                new EmailFieldMasker(),
                new AddressFieldMasker())));
    }
}
