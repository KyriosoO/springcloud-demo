package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.config.AgentMetadataReloader;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPortImpl;
import com.dylan.agent.metadata.domain.internal.DomainMetadataPropertiesValidator;
import com.dylan.agent.metadata.domain.internal.DomainMetadataStore;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

import javax.crypto.spec.SecretKeySpec;

class AgentMetadataReloadTest {
    @Test
    void rejectsSameBundleVersionWithDifferentDigest() {
        var current = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        AgentMetadataReloader reloader = new AgentMetadataReloader(
                new AgentMetadataStore(current),
                domainPort(),
                payloadKeyProvider(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> reloader.publishValidated(
                MetadataTestSupport.bundle("bundle-v1", "digest-v2")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("same metadata bundleVersion");
    }

    @Test
    void validatesPolicyRequiredMaskFieldReferences() {
        var current = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        AgentMetadataReloader reloader = new AgentMetadataReloader(
                new AgentMetadataStore(current),
                domainPort(),
                payloadKeyProvider(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var unknownField = new CanonicalFieldRef("employee", "unknownField");
        var candidate = MetadataTestSupport.bundleWithEmployeeFieldSecurity(
                "bundle-v2",
                "digest-v2",
                Map.of(unknownField, new DomainSecurityConstraints.FieldSecurityConstraint(
                        true,
                        true,
                        Set.of(AgentOperator.EQ),
                        Set.of(),
                        Optional.of(MaskType.ID_CARD))));

        assertThatThrownBy(() -> reloader.publishValidated(candidate))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unknown field reference");
    }

    @Test
    void rejectsReloadWhenActivePayloadKeyCannotBeResolved() {
        var current = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        AgentMetadataReloader reloader = new AgentMetadataReloader(
                new AgentMetadataStore(current),
                domainPort(),
                payloadKeyProvider(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var candidate = MetadataTestSupport.bundleWithActivePayloadKeyId("bundle-v2", "digest-v2", "MISSING");

        assertThatThrownBy(() -> reloader.publishValidated(candidate))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing payload key");
    }

    @Test
    void securitySettingsRegistryReadsPublishedBundle() {
        var current = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        AgentMetadataStore store = new AgentMetadataStore(current);
        AgentSecuritySettingsRegistry registry = new AgentSecuritySettingsRegistry(store);
        AgentMetadataReloader reloader = new AgentMetadataReloader(
                store,
                domainPort(),
                payloadKeyProvider(Set.of("ACTIVE", "NEXT")),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var candidate = MetadataTestSupport.bundleWithActivePayloadKeyId("bundle-v2", "digest-v2", "NEXT");
        reloader.publishValidated(candidate);

        assertThat(registry.current().activePayloadKeyId()).isEqualTo("NEXT");
    }

    private PayloadKeyProvider payloadKeyProvider() {
        return payloadKeyProvider(Set.of("ACTIVE"));
    }

    private PayloadKeyProvider payloadKeyProvider(Set<String> keyIds) {
        return keyId -> {
            if (keyIds.contains(keyId)) {
                return new SecretKeySpec(new byte[32], "AES");
            }
            throw new IllegalStateException("missing payload key: " + keyId);
        };
    }

    private DomainMetadataPortImpl domainPort() {
        GenericApplicationContext context = new GenericApplicationContext();
        context.registerBean("employeeAgentAdapter", DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.registerBean("transactionAgentAdapter", DomainMetadataTestSupport.QueryableAggregatableAdapter.class,
                DomainMetadataTestSupport.QueryableAggregatableAdapter::new);
        context.refresh();
        var store = new DomainMetadataStore(DomainMetadataPropertiesValidator.build(
                DomainMetadataTestSupport.properties(),
                context.getBeansOfType(com.dylan.agent.adapter.api.AgentAdapterPort.class),
                DomainMetadataTestSupport.TEST_CLOCK));
        return new DomainMetadataPortImpl(store, context, DomainMetadataTestSupport.TEST_CLOCK);
    }
}
