package com.dylan.baseline.agent.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashSet;
import org.junit.jupiter.api.Test;

class RuntimeCompatibilityGateTest {
    private final RuntimeCompatibilityGate gate = new RuntimeCompatibilityGate();

    @Test
    void loadsLockAndAllowsExactMatch() {
        ContractMetadata expected = new ContractLockMetadataLoader(new ObjectMapper()).load();
        RuntimeCompatibilityDecision decision = gate.evaluate(expected, copy(expected), null);
        assertThat(decision.status()).isEqualTo(RuntimeCompatibilityStatus.ALLOW);
        assertThat(decision.reason()).isEqualTo(RuntimeCompatibilityReason.COMPATIBLE);
    }

    @Test
    void rejectsInStablePriorityOrder() {
        ContractMetadata expected = metadata("1.0.0", fingerprint('a'), "a");
        assertThat(gate.evaluate(expected, null, "a").reason()).isEqualTo(RuntimeCompatibilityReason.METADATA_INVALID);
        assertThat(gate.evaluate(expected, metadata("2.0.0", fingerprint('b'), "a"), "a").reason())
                .isEqualTo(RuntimeCompatibilityReason.VERSION_MISMATCH);
        assertThat(gate.evaluate(expected, metadata("1.0.0", fingerprint('b'), "a"), "a").reason())
                .isEqualTo(RuntimeCompatibilityReason.FINGERPRINT_MISMATCH);
        assertThat(gate.evaluate(expected, metadata("1.0.0", fingerprint('a')), "a").reason())
                .isEqualTo(RuntimeCompatibilityReason.CAPABILITY_MISSING);
    }

    @Test
    void rejectsMalformedLockMetadata() {
        ContractLockMetadataLoader loader = new ContractLockMetadataLoader(new ObjectMapper());
        String validPrefix = """
                {"lockFormatVersion":1,"sourcePath":"agent-api/src/main/resources/openapi/agent-runtime-openapi.json",
                "sourceSha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "contractFingerprint":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "contractVersion":"1.0.0","capabilities":%s}
                """;
        for (String capabilities : java.util.List.of("{}", "[\"b\",\"a\"]", "[\"a\",\"a\"]", "[null]")) {
            assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> loader.load(new ByteArrayInputStream(
                    validPrefix.formatted(capabilities).getBytes(StandardCharsets.UTF_8)))))
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessage("CONTRACT_LOCK_INVALID");
        }
        String mismatchedFingerprint = validPrefix.formatted("[]").replace("sha256:aaaaaaaa", "sha256:baaaaaaa");
        assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> loader.load(new ByteArrayInputStream(
                mismatchedFingerprint.getBytes(StandardCharsets.UTF_8)))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("CONTRACT_LOCK_INVALID");
        for (String malformedJson : java.util.List.of(
                validPrefix.formatted("[]").replace(
                        "{\"lockFormatVersion\":1", "{\"lockFormatVersion\":1,\"lockFormatVersion\":1"),
                validPrefix.formatted("[]") + "{}")) {
            assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> loader.load(new ByteArrayInputStream(
                    malformedJson.getBytes(StandardCharsets.UTF_8)))))
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessage("CONTRACT_LOCK_INVALID");
        }
    }

    private static ContractMetadata metadata(String version, String fingerprint, String... capabilities) {
        return new ContractMetadata().contractVersion(version).contractFingerprint(fingerprint)
                .capabilities(new LinkedHashSet<>(java.util.List.of(capabilities)));
    }

    private static ContractMetadata copy(ContractMetadata source) {
        return metadata(source.getContractVersion(), source.getContractFingerprint(),
                source.getCapabilities().toArray(String[]::new));
    }

    private static String fingerprint(char value) {
        return "sha256:" + String.valueOf(value).repeat(64);
    }
}
