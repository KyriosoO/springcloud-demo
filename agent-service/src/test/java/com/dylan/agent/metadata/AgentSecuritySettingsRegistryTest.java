package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;

class AgentSecuritySettingsRegistryTest {
    @Test
    void replacesSettingsAtomicallyForReload() {
        AgentSecuritySettingsRegistry registry = new AgentSecuritySettingsRegistry(
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ofMinutes(5), 10, "ACTIVE"));

        registry.replaceForReload(new AgentSecuritySettings(Duration.ofMinutes(30), Duration.ZERO, 5, "NEXT"));

        assertThat(registry.current().activePayloadKeyId()).isEqualTo("NEXT");
        assertThat(registry.current().globalMaxContextTtl()).isEqualTo(Duration.ofMinutes(30));
    }
}
