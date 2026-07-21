package com.dylan.documentprovider;

import org.springframework.stereotype.Component;
import java.time.Clock;
import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

/** 实例内短窗重复写检测；不宣称集群 exactly-once。 */
@Component
final class DocumentProviderReplayGuard {
    private static final int MAX_ENTRIES = 10_000;
    private final ConcurrentHashMap<ReplayKey, Long> seen = new ConcurrentHashMap<>();
    private final Clock clock = Clock.systemUTC();

    boolean register(String serviceIdentity, String operationId, String requestDigest) {
        long now = clock.millis();
        if (seen.size() >= MAX_ENTRIES) {
            seen.entrySet().removeIf(entry -> entry.getValue() <= now);
            if (seen.size() >= MAX_ENTRIES) return false;
        }
        ReplayKey key = new ReplayKey(serviceIdentity, operationId, requestDigest);
        AtomicBoolean accepted = new AtomicBoolean();
        seen.compute(key, (ignored, expiresAt) -> {
            if (expiresAt == null || expiresAt <= now) {
                accepted.set(true);
                return now + Duration.ofMinutes(5).toMillis();
            }
            return expiresAt;
        });
        return accepted.get();
    }

    private record ReplayKey(String serviceIdentity, String operationId, String requestDigest) {}
}
