package com.dylan.agent.kernel.config;

import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;
import java.util.Set;

/**
 * Capability Kernel composition root.
 *
 * <p>No domain facts or adapter instances are owned here.</p>
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnBean(CapabilityRegistration.class)
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
                                                 CapabilityRegistrationValidator validator) {
        return new CapabilityRegistry(registrations, validator, contracts, Set.of());
    }
}
