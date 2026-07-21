package com.dylan.baseline.agent;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.Locale;
import java.util.Objects;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.cloud.client.serviceregistry.ServiceRegistry;
import org.springframework.context.ApplicationContext;
import org.springframework.core.env.Environment;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AgentServiceApplicationTest {

    @Autowired
    private ApplicationContext applicationContext;

    @Autowired
    private Environment environment;

    @Test
    void startsAsAnIsolatedEmptyService() {
        assertThat(environment.getProperty("server.port")).isEqualTo("0");
        assertThat(environment.getProperty("spring.cloud.config.enabled")).isEqualTo("false");
        assertThat(environment.getProperty("spring.cloud.discovery.enabled")).isEqualTo("false");
        assertThat(environment.getProperty("spring.cloud.service-registry.auto-registration.enabled"))
                .isEqualTo("false");
        assertThat(environment.getProperty("eureka.client.enabled")).isEqualTo("false");
        assertThat(environment.getProperty("eureka.client.register-with-eureka")).isEqualTo("false");
        assertThat(environment.getProperty("eureka.client.fetch-registry")).isEqualTo("false");

        assertThat(applicationContext.getBeansOfType(DiscoveryClient.class).values())
                .allSatisfy(client -> {
                    assertThat(client.getClass().getName()).matches(".*(Simple|Composite)DiscoveryClient");
                    assertThat(client.getServices()).isEmpty();
                });
        assertThat(applicationContext.getBeansOfType(ServiceRegistry.class)).isEmpty();

        var applicationTypes = Arrays.stream(applicationContext.getBeanDefinitionNames())
                .map(applicationContext::getType)
                .filter(Objects::nonNull)
                .filter(type -> type.getPackageName().startsWith("com.dylan.baseline.agent"))
                .toList();
        assertThat(applicationTypes).containsExactly(AgentServiceApplication.class);

        var forbiddenInfrastructureTypes = Arrays.stream(applicationContext.getBeanDefinitionNames())
                .map(applicationContext::getType)
                .filter(Objects::nonNull)
                .map(Class::getName)
                .map(name -> name.toLowerCase(Locale.ROOT))
                .filter(name -> name.contains("flyway")
                        || name.contains("elasticsearch")
                        || name.contains("openfeign")
                        || name.contains("vendorclient"))
                .toList();
        assertThat(forbiddenInfrastructureTypes).isEmpty();
    }
}
