package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.lifecycle.port.ContextScopeRetirementParticipant;
import com.dylan.agent.metadata.context.migration.ContextMigrationRegistry;
import com.dylan.agent.metadata.context.migration.QueryContextPayloadV10ToV12Migrator;
import com.dylan.agent.metadata.context.migration.QueryContextPayloadV11ToV12Migrator;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

import java.time.Clock;
import java.util.List;

/**
 * Context 边界装配根。
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnBean({ContextRepository.class, PayloadJsonCodec.class, ProtectedPayloadCodec.class})
@EnableConfigurationProperties(ContextStorageProperties.class)
public class ContextSecurityConfiguration {

    @Bean
    ContextBoundary contextBoundary(ContextRepository repository,
                                     PayloadJsonCodec payloadJsonCodec,
                                     ProtectedPayloadCodec protectedPayloadCodec,
                                     ContextMigrationRegistry contextMigrationRegistry,
                                     Clock clock) {
        return new ContextBoundary(repository, payloadJsonCodec, protectedPayloadCodec, contextMigrationRegistry, clock);
    }

    @Bean
    ContextMigrationRegistry contextMigrationRegistry() {
        return new ContextMigrationRegistry(List.of(
                new QueryContextPayloadV10ToV12Migrator(),
                new QueryContextPayloadV11ToV12Migrator()));
    }

    @Bean
    ContextFinalizationParticipant contextFinalizationParticipant(
            ContextRepository repository,
            PayloadJsonCodec payloadJsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            Clock clock) {
        return new ContextFinalizationParticipantImpl(
                repository,
                payloadJsonCodec,
                protectedPayloadCodec,
                clock);
    }

    @Bean
    ContextScopeRetirementParticipant contextScopeRetirementParticipant(ContextRepository repository) {
        return new ContextScopeRetirementParticipantImpl(repository);
    }
}
