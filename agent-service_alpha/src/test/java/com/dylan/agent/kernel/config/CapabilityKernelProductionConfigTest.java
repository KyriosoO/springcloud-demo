package com.dylan.agent.kernel.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.io.ClassPathResource;

class CapabilityKernelProductionConfigTest {

    @Test
    void productionConfigurationEnablesKernelRegistrations() {
        YamlPropertiesFactoryBean yaml = new YamlPropertiesFactoryBean();
        yaml.setResources(new ClassPathResource("application.yml"));

        assertThat(yaml.getObject())
                .isNotNull()
                .containsEntry("agent.kernel.enabled", Boolean.TRUE);
    }
}
