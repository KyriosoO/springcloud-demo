package com.dylan.agent.capability.document.governance.emergency;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentEmergencyTargetRefTest {
    @Test
    void rejectsWildcardProfileAndNonDigestPhysicalTargets() {
        assertThatThrownBy(() -> new DocumentEmergencyTargetRef.ProfileTarget("profile-*"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new DocumentEmergencyTargetRef.IndexTarget("physical-index-name"))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("SHA-256");
        assertThatThrownBy(() -> new DocumentEmergencyTargetRef.ProviderBindingTarget("provider-name"))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("SHA-256");
    }
}
