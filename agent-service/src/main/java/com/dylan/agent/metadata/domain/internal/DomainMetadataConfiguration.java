package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.kernel.port.DomainExecutionPort;
import com.dylan.agent.metadata.domain.DomainSecurityBoundary;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;

import java.time.Clock;
import java.util.Map;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** D04 domain metadata 的 Spring 装配根。 */
@Configuration
@EnableConfigurationProperties(DomainMetadataProperties.class)
public class DomainMetadataConfiguration {

    @Bean
    DomainMetadataStore domainMetadataStore(
            DomainMetadataProperties properties,
            Map<String, AgentAdapterPort> adapterPorts,
            Clock clock) {
        return new DomainMetadataStore(
                DomainMetadataPropertiesValidator.build(properties, adapterPorts, clock));
    }

    @Bean
    DomainMetadataPort domainMetadataPort(
            DomainMetadataStore store,
            ApplicationContext applicationContext,
            Clock clock) {
        return new DomainMetadataPortImpl(store, applicationContext, clock);
    }

    @Bean
    DomainCatalogView domainCatalogView(DomainMetadataStore store) {
        return new DomainCatalogView(store);
    }

    @Bean
    DomainExecutionPort domainExecutionPort(DomainMetadataPort domainMetadataPort) {
        return new DomainSecurityBoundary(domainMetadataPort);
    }
}
