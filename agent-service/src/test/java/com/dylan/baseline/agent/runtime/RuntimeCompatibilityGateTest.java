package com.dylan.baseline.agent.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;
import com.fasterxml.jackson.databind.ObjectMapper;
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
