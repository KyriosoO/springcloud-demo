package com.dylan.baseline.agent;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.baseline.agent.security.authorization.AuthPermissionAuthorityPort;
import com.dylan.baseline.agent.security.policy.admin.FailClosedSecurityChangeApprovalEvidencePort;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService;
import com.dylan.common.security.ServiceTokenProvider;
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

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "common.security.secrets.allow-config-values=true",
                "common.security.secrets.source-order[0]=config",
                "common.security.secrets.jwt.active-key-id=ACTIVE",
                "common.security.secrets.jwt.keys.ACTIVE.value=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        })
class AgentServiceApplicationTest {

    @Autowired
    private ApplicationContext applicationContext;

    @Autowired
    private Environment environment;

    @Test
    void startsWithFailClosedSecurityWiringAndNoExternalRegistration() {
        assertThat(environment.getProperty("server.port")).isEqualTo("0");
        assertThat(environment.getProperty("spring.cloud.config.enabled")).isEqualTo("false");
        assertThat(environment.getProperty("spring.cloud.discovery.enabled")).isEqualTo("false");
        assertThat(environment.getProperty("spring.cloud.service-registry.auto-registration.enabled"))
                .isEqualTo("false");
        assertThat(environment.getProperty("eureka.client.enabled")).isEqualTo("false");
        assertThat(environment.getProperty("eureka.client.register-with-eureka")).isEqualTo("false");
        assertThat(environment.getProperty("eureka.client.fetch-registry")).isEqualTo("false");
        assertThat(environment.getProperty("agent.security.auth.positive-cache-enabled")).isEqualTo("false");
        assertThat(environment.getProperty("agent.security.auth.base-url")).isEqualTo("http://localhost:8090");
        assertThat(environment.getProperty("agent.security.policy.required")).isEqualTo("true");
        assertThat(environment.getProperty("agent.security.policy.persistence-enabled")).isEqualTo("false");
        assertThat(environment.getProperty("agent.security.auth-field-migration-mode")).isEqualTo("SEED_ONLY");

        assertThat(applicationContext.getBeansOfType(DiscoveryClient.class).values())
                .allSatisfy(client -> {
                    assertThat(client.getClass().getName()).matches(".*(Simple|Composite)DiscoveryClient");
                    assertThat(client.getServices()).isEmpty();
                });
        assertThat(applicationContext.getBeansOfType(ServiceRegistry.class)).isEmpty();

        assertThat(applicationContext.getBean(AuthPermissionAuthorityPort.class)).isNotNull();
        assertThat(applicationContext.getBean(ServiceTokenProvider.class)).isNotNull();
        assertThat(applicationContext.getBean(SecurityChangeApprovalEvidencePort.class))
                .isInstanceOf(FailClosedSecurityChangeApprovalEvidencePort.class);
        assertThat(applicationContext.getBeansOfType(SecurityPolicyAdministrationRepository.class)).isEmpty();
        assertThat(applicationContext.getBeansOfType(SecurityPolicyAdministrationService.class)).isEmpty();

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
