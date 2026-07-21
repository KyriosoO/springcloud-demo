package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.metadata.domain.port.DomainAdapterKey;

import org.springframework.context.ApplicationContext;

import java.time.Clock;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 以当前 Spring bean 装配作为受控 availability signal；异常统一按不可用处理。 */
public final class SpringBeanAdapterAvailabilityResolver implements AdapterAvailabilityResolver {

    private final DomainMetadataStore store;
    private final ApplicationContext applicationContext;
    private final Clock clock;

    public SpringBeanAdapterAvailabilityResolver(
            DomainMetadataStore store,
            ApplicationContext applicationContext,
            Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.applicationContext = Objects.requireNonNull(applicationContext);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public AdapterDeploymentAvailability capture(Set<DomainAdapterKey> keys, Instant absoluteDeadline) {
        Objects.requireNonNull(keys, "keys must not be null");
        Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
        DomainMetadataStaticBundle bundle = store.current();
        Map<DomainAdapterKey, AdapterDeploymentAvailability.Entry> entries = new LinkedHashMap<>();
        for (DomainAdapterKey key : keys.stream().sorted().toList()) {
            entries.put(key, resolve(bundle, key, absoluteDeadline));
        }
        return AdapterDeploymentAvailability.capture(entries, clock.instant());
    }

    private AdapterDeploymentAvailability.Entry resolve(
            DomainMetadataStaticBundle bundle,
            DomainAdapterKey key,
            Instant absoluteDeadline) {
        if (!clock.instant().isBefore(absoluteDeadline)) {
            return unavailable(AdapterDeploymentAvailability.ReasonCode.DEADLINE_EXCEEDED);
        }
        AdapterRegistration registration = bundle.registrations().find(key.role(), key.domain()).orElse(null);
        if (registration == null || !applicationContext.containsBean(registration.portBeanName())) {
            return unavailable(AdapterDeploymentAvailability.ReasonCode.BEAN_MISSING);
        }
        try {
            AgentAdapterPort port = applicationContext.getBean(registration.portBeanName(), AgentAdapterPort.class);
            if (!AdapterRolePortTypes.requirePortType(key.role()).isInstance(port)) {
                return unavailable(AdapterDeploymentAvailability.ReasonCode.PORT_TYPE_MISMATCH);
            }
            return new AdapterDeploymentAvailability.Entry(
                    AdapterDeploymentAvailability.Status.AVAILABLE,
                    AdapterDeploymentAvailability.ReasonCode.AVAILABLE);
        } catch (RuntimeException ex) {
            return unavailable(AdapterDeploymentAvailability.ReasonCode.UNKNOWN);
        }
    }

    private static AdapterDeploymentAvailability.Entry unavailable(
            AdapterDeploymentAvailability.ReasonCode reasonCode) {
        return new AdapterDeploymentAvailability.Entry(
                AdapterDeploymentAvailability.Status.UNAVAILABLE, reasonCode);
    }
}
