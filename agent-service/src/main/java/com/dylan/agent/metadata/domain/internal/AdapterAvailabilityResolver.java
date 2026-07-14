package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.metadata.domain.port.DomainAdapterKey;

import java.time.Instant;
import java.util.Set;

/** 请求级捕获受控 Adapter deployment/health signal 的内部端口。 */
public interface AdapterAvailabilityResolver {
    AdapterDeploymentAvailability capture(Set<DomainAdapterKey> keys, Instant absoluteDeadline);
}
