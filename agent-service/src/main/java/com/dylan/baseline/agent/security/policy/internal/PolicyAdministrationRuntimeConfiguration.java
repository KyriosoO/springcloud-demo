package com.dylan.baseline.agent.security.policy.internal;

import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator;
import com.dylan.baseline.agent.security.policy.admin.FailClosedSecurityChangeApprovalEvidencePort;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class PolicyAdministrationRuntimeConfiguration {

    @Bean
    @ConditionalOnMissingBean
    SecurityChangeApprovalEvidencePort securityChangeApprovalEvidencePort() {
        return new FailClosedSecurityChangeApprovalEvidencePort();
    }

    @Bean
    AuthFieldPolicyPayloadValidator authFieldPolicyPayloadValidator(ObjectMapper objectMapper) {
        return new AuthFieldPolicyPayloadValidator(objectMapper);
    }

    @Bean
    @ConditionalOnBean(SecurityPolicyAdministrationRepository.class)
    SecurityPolicyAdministrationService securityPolicyAdministrationService(
            SecurityPolicyAdministrationRepository repository,
            SecurityChangeApprovalEvidencePort approvalEvidencePort,
            AuthFieldPolicyPayloadValidator payloadValidator,
            Clock clock) {
        return new SecurityPolicyAdministrationService(repository, approvalEvidencePort, payloadValidator, clock);
    }
}
