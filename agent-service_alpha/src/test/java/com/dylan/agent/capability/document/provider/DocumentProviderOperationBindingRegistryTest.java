package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProviderOperationBindingRegistryTest {

    @Test
    void handsOffExactBindingOnlyOnce() {
        var context = DocumentCapabilityHandlerTestSupport.context((request, operationContext) -> null);
        Clock clock = Clock.fixed(
                context.executionScope().recheckedAt().plusMillis(1), ZoneOffset.UTC);
        var operationContext = context.operationContext(CapabilityOperationType.of("DOCUMENT_GENERATION"));
        var provider = new ProviderSafeIdentity("provider", Optional.empty());
        var binding = new DocumentProviderBindingReference(
                operationContext.operationType(), provider, "adapter", "deployment", "vendor-v1",
                "a".repeat(64), "b".repeat(64));
        var metadata = new CapabilityOperationMetadata(
                operationContext.operationId(), operationContext.operationType(), provider,
                1, 1, CapabilityOperationTermination.SUCCEEDED, "diagnostic",
                context.resourceLimits().reference(), false, false, false);
        var registry = new DocumentProviderOperationBindingRegistry(clock);

        registry.publish(operationContext.operationId(), binding, context.absoluteDeadline());

        assertThat(registry.consume(metadata)).isEqualTo(binding);
        assertThatThrownBy(() -> registry.consume(metadata))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("missing or mismatched");
    }
}
