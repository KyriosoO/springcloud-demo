package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;
import com.dylan.agent.capability.document.governance.validation.DocumentValidationModels;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class DocumentProviderActivationCoordinatorTest {
    @Test
    void failClosedCoveragePreventsInitialProviderActivation() {
        Instant now = Instant.parse("2026-07-14T08:00:00Z");
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        var canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper().findAndRegisterModules());
        var operation = CapabilityOperationType.of("DOCUMENT_GENERATION");
        var provider = new ProviderSafeIdentity("provider-safe", Optional.of("model-safe"));
        String bindingDigest = canonicalizer.providerBindingDigest(
                operation, provider, "document-provider-adapter", "deployment-1", "vendor-v1", "a".repeat(64));
        var binding = new DocumentProviderBindingReference(operation, provider,
                "document-provider-adapter", "deployment-1", "vendor-v1", "a".repeat(64), bindingDigest);
        String unit = DocumentProviderActivationCoordinator.unitKeyDigest(operation);
        String expected = canonical("PROVIDER-MISSING-1", operation.value());
        String report = "b".repeat(64);
        String approval = "approval-safe";
        Instant expires = now.plusSeconds(30);
        String gateDigest = canonical("DRG-1", "PROVIDER_OPERATION", unit, expected,
                bindingDigest, report, approval, now.toString(), expires.toString());
        var gate = new DocumentValidationModels.ReleaseGateEvidence(
                "DRG-" + gateDigest.substring(0, 20), "PROVIDER_OPERATION", unit, expected,
                bindingDigest, report, approval, now, expires, gateDigest);
        var coordinator = new DocumentProviderActivationCoordinator(jdbc,
                Clock.fixed(now, ZoneOffset.UTC), java.time.Duration.ofMinutes(2), canonicalizer);

        assertThatThrownBy(() -> coordinator.activate(binding, "rollout-1", "change-1", gate, Map.of()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("coverage required");
        verifyNoInteractions(jdbc);
    }

    private static String canonical(String... values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
