package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.lifecycle.port.ContextScopeRetirementParticipant;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;

/**
 * Context 边界装配根。
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnBean({ContextRepository.class, PayloadJsonCodec.class, ProtectedPayloadCodec.class})
public class ContextSecurityConfiguration {

    @Bean
    ContextBoundary contextBoundary(ContextRepository repository,
                                     PayloadJsonCodec payloadJsonCodec,
                                     ProtectedPayloadCodec protectedPayloadCodec,
                                     AgentSecuritySettingsRegistry settingsRegistry,
                                     Clock clock) {
        return new ContextBoundary(repository, payloadJsonCodec, protectedPayloadCodec, settingsRegistry, clock);
    }

    @Bean
    @ConditionalOnBean(AgentSecuritySettingsRegistry.class)
    ContextFinalizationParticipant contextFinalizationParticipant(
            ContextRepository repository,
            PayloadJsonCodec payloadJsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            AgentSecuritySettingsRegistry settingsRegistry,
            Clock clock) {
        return new ContextFinalizationParticipantImpl(
                repository,
                payloadJsonCodec,
                protectedPayloadCodec,
                settingsRegistry,
                clock);
    }

    @Bean
    ContextScopeRetirementParticipant contextScopeRetirementParticipant(ContextRepository repository) {
        return new ContextScopeRetirementParticipantImpl(repository);
    }
}
