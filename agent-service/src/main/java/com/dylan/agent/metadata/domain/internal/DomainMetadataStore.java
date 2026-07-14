package com.dylan.agent.metadata.domain.internal;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

import com.dylan.agent.metadata.domain.port.DomainMetadataStaticEvidence;

/** D04 静态 bundle 的原子发布存储。 */
public final class DomainMetadataStore {

    private final AtomicReference<DomainMetadataStaticBundle> current;

    public DomainMetadataStore(DomainMetadataStaticBundle initial) {
        this.current = new AtomicReference<>(Objects.requireNonNull(initial, "initial bundle must not be null"));
    }

    public DomainMetadataStaticBundle current() {
        return current.get();
    }

    public boolean publish(
            DomainMetadataStaticEvidence expected,
            DomainMetadataStaticBundle candidate) {
        Objects.requireNonNull(expected, "expected evidence must not be null");
        Objects.requireNonNull(candidate, "candidate must not be null");
        DomainMetadataStaticBundle active = current.get();
        if (!active.staticEvidence().equals(expected)) {
            return false;
        }
        if (active.staticEvidence().catalogVersion().equals(candidate.staticEvidence().catalogVersion())
                && !active.staticEvidence().catalogDigest().equals(candidate.staticEvidence().catalogDigest())) {
            throw new IllegalStateException("METADATA_VERSION_REUSED: catalog");
        }
        if (active.staticEvidence().registrationSetVersion()
                .equals(candidate.staticEvidence().registrationSetVersion())
                && !active.staticEvidence().registrationDigest()
                .equals(candidate.staticEvidence().registrationDigest())) {
            throw new IllegalStateException("METADATA_VERSION_REUSED: registration");
        }
        return current.compareAndSet(active, candidate);
    }
}
