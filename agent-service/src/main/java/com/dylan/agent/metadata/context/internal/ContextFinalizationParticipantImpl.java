package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.RunScope;
import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Instant;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/**
 * Persists approved context writes inside Lifecycle SUCCESS transaction.
 */
public final class ContextFinalizationParticipantImpl implements ContextFinalizationParticipant {

    private final ContextRepository repository;
    private final PayloadJsonCodec jsonCodec;
    private final ProtectedPayloadCodec protectedPayloadCodec;
    private final AgentSecuritySettingsRegistry settingsRegistry;
    private final Clock clock;

    public ContextFinalizationParticipantImpl(
            ContextRepository repository,
            PayloadJsonCodec jsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            AgentSecuritySettingsRegistry settingsRegistry,
            Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.jsonCodec = Objects.requireNonNull(jsonCodec);
        this.protectedPayloadCodec = Objects.requireNonNull(protectedPayloadCodec);
        this.settingsRegistry = Objects.requireNonNull(settingsRegistry);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    @Transactional(propagation = Propagation.MANDATORY)
    public void persist(List<ApprovedContextWrite> writes) {
        List<ApprovedContextWrite> ordered = List.copyOf(writes == null ? List.of() : writes).stream()
                .sorted(Comparator.comparing(write -> write.candidate().contextType().name()))
                .toList();
        for (ApprovedContextWrite write : ordered) {
            assertStrictExpiry(write);
            byte[] plaintext = jsonCodec.serialize(
                    write.candidate().payload(),
                    write.candidate().payload().getClass());
            var protectedPayload = protectedPayloadCodec.encrypt(
                    plaintext,
                    protectionContext(write));
            repository.upsertApproved(
                    new ContextRecordEntity(
                            write.contextId(),
                            write.recordKey(),
                            write.contractRef(),
                            write.expectedVersion().targetVersion(),
                            protectedPayload,
                            write.sourceCapabilityId(),
                            write.sourceInvocationId(),
                            write.sourceDomain().orElse(null),
                            write.expiresAt()),
                    write.expectedVersion());
        }
    }

    private void assertStrictExpiry(ApprovedContextWrite write) {
        Instant maxAllowed = clock.instant().plus(settingsRegistry.current().globalMaxContextTtl());
        if (write.expiresAt().isAfter(maxAllowed)) {
            throw new IllegalStateException("approved context write exceeds current globalMaxContextTtl");
        }
    }

    private PayloadProtectionContext protectionContext(ApprovedContextWrite write) {
        return new PayloadProtectionContext(
                PayloadPurpose.CONTEXT_PAYLOAD,
                write.contextId(),
                write.contractRef(),
                contextBindingDigest(write));
    }

    private String contextBindingDigest(ApprovedContextWrite write) {
        String canonical = String.join("|",
                write.recordKey().owner().type(),
                write.recordKey().owner().id(),
                scopeType(write),
                write.recordKey().scope().scopeId(),
                write.recordKey().contextType().name(),
                write.sourceCapabilityId(),
                write.sourceInvocationId(),
                write.sourceDomain().orElse(""),
                Long.toString(write.expectedVersion().targetVersion()));
        return sha256Hex(canonical);
    }

    private String scopeType(ApprovedContextWrite write) {
        if (write.recordKey().scope() instanceof ConversationScope) {
            return "CONVERSATION";
        }
        if (write.recordKey().scope() instanceof RunScope) {
            return "RUN";
        }
        throw new IllegalArgumentException("unsupported context scope type: "
                + write.recordKey().scope().getClass().getName());
    }

    private String sha256Hex(String canonical) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (Exception ex) {
            throw new IllegalStateException("failed to compute context binding digest", ex);
        }
    }
}
