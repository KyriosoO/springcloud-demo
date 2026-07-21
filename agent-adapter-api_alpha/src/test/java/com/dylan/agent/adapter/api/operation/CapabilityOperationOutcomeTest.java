package com.dylan.agent.adapter.api.operation;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CapabilityOperationOutcomeTest {

    private static final ResourceLimitReference LIMITS = new ResourceLimitReference(
            AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
            "a".repeat(64), "inv-1", "registration-v1");

    @Test
    void returnsOnlySuccessBoundToTheExpectedOperationAndLimits() {
        CapabilityOperationContext context = context();
        CapabilityOperationSuccess<String> success = new CapabilityOperationSuccess<>(
                "candidate", metadata(context.operationId(), context.operationType(),
                        CapabilityOperationTermination.SUCCEEDED, 1, false, false));

        assertThat(CapabilityOperationOutcomes.requireBoundSuccess(success, context))
                .isEqualTo("candidate");

        CapabilityOperationSuccess<String> mismatched = new CapabilityOperationSuccess<>(
                "candidate", metadata("other-operation", context.operationType(),
                        CapabilityOperationTermination.SUCCEEDED, 1, false, false));
        assertThatThrownBy(() -> CapabilityOperationOutcomes.requireBoundSuccess(mismatched, context))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("binding mismatch");
    }

    @Test
    void rejectsInconsistentTerminalMetadata() {
        CapabilityOperationContext context = context();
        assertThatThrownBy(() -> metadata(
                context.operationId(), context.operationType(),
                CapabilityOperationTermination.SUCCEEDED, 1, true, false))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("deadline or cancellation");

        CapabilityOperationMetadata rejected = metadata(
                context.operationId(), context.operationType(),
                CapabilityOperationTermination.REJECTED, 0, false, false);
        assertThatThrownBy(() -> new CapabilityOperationFailure<String>(
                CapabilityOperationFailureCode.PROVIDER_FAILED, "diagnostic", rejected))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("code/termination mismatch");
    }

    private static CapabilityOperationContext context() {
        CapabilityResourceLimitView limits = new CapabilityResourceLimitView() {
            @Override
            public <T extends CapabilityResourceLimit> T require(
                    com.dylan.agent.api.contract.common.ContractRef ref, Class<T> type) {
                throw new UnsupportedOperationException();
            }

            @Override
            public ResourceLimitReference reference() {
                return LIMITS;
            }
        };
        return new CapabilityOperationContext(
                "inv-1", "corr-1", "query.search", "operation-1",
                CapabilityOperationType.of("QUERY_SEARCH"),
                Instant.parse("2099-01-01T00:00:00Z"), () -> false, limits);
    }

    private static CapabilityOperationMetadata metadata(
            String operationId,
            CapabilityOperationType operationType,
            CapabilityOperationTermination termination,
            int attempts,
            boolean deadlineTouched,
            boolean cancellationObserved) {
        return new CapabilityOperationMetadata(
                operationId, operationType,
                new ProviderSafeIdentity("provider", Optional.empty()),
                attempts, 1, termination, "diagnostic", LIMITS,
                false, deadlineTouched, cancellationObserved);
    }
}
