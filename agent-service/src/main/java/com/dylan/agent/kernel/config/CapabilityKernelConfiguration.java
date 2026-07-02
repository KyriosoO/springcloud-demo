package com.dylan.agent.kernel.config;

import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.core.ExecutionCore;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.kernel.port.ContextApprovalPort;
import com.dylan.agent.kernel.port.ContextExecutionPort;
import com.dylan.agent.kernel.port.DomainExecutionPort;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.util.List;

/**
 * 能力内核装配根。
 *
 * <p>这里不持有领域事实或适配器实例。</p>
 */
@Configuration(proxyBeanMethods = false)
public class CapabilityKernelConfiguration {

    @Bean
    public ContractRegistry contractRegistry(List<CapabilityRegistration<?, ?, ?>> registrations) {
        if (registrations.isEmpty()) {
            throw new IllegalStateException("at least one CapabilityRegistration required");
        }
        return ContractRegistry.from(registrations);
    }

    @Bean
    public CapabilityRegistry capabilityRegistry(List<CapabilityRegistration<?, ?, ?>> registrations,
                                                 ContractRegistry contracts,
                                                 CapabilityRegistrationValidator validator,
                                                 DomainMetadataPort domainMetadataPort) {
        return new CapabilityRegistry(registrations, validator, contracts, domainMetadataPort.knownRoles());
    }

    @Bean
    public ExecutionCore executionCore(AuthorizationExecutionPort authorizationExecutionPort,
                                       ContextExecutionPort contextExecutionPort,
                                       DomainExecutionPort domainExecutionPort,
                                       ContextApprovalPort contextApprovalPort,
                                       ResultSecurityPort resultSecurityPort,
                                       Clock clock) {
        return new ExecutionCore(
                authorizationExecutionPort,
                contextExecutionPort,
                domainExecutionPort,
                contextApprovalPort,
                resultSecurityPort,
                clock);
    }
}
