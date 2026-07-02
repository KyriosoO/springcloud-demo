package com.dylan.authcenter.agent.permission;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
                "eureka.client.enabled=false",
                "spring.cloud.config.enabled=false"
        })
@DisplayName("AgentPermission Spring context")
class AgentPermissionSpringContextTest {

    @Autowired
    private AgentPermissionProjectionService projectionService;

    @Autowired
    private AgentPermissionInternalController internalController;

    @Test
    void wiresInternalPermissionProjectionBeans() {
        assertThat(projectionService).isNotNull();
        assertThat(internalController).isNotNull();
    }
}
