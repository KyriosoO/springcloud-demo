package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/**
 * 在生命周期成功事务内持久化已审批的 Context 写入。
 */
public class ContextFinalizationParticipantImpl implements ContextFinalizationParticipant {

    private final ContextRepository repository;
    private final PayloadJsonCodec jsonCodec;
    private final ProtectedPayloadCodec protectedPayloadCodec;
    private final Clock clock;

    public ContextFinalizationParticipantImpl(
            ContextRepository repository,
            PayloadJsonCodec jsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.jsonCodec = Objects.requireNonNull(jsonCodec);
        this.protectedPayloadCodec = Objects.requireNonNull(protectedPayloadCodec);
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
                            true,
                            write.expiresAt()),
                    write.expectedVersion());
        }
    }

    private void assertStrictExpiry(ApprovedContextWrite write) {
        if (!write.expiresAt().isAfter(clock.instant())) {
            throw new IllegalStateException("approved context write must expire in the future");
        }
    }

    private PayloadProtectionContext protectionContext(ApprovedContextWrite write) {
        return new PayloadProtectionContext(
                PayloadPurpose.CONTEXT_PAYLOAD,
                write.contextId(),
                write.contractRef(),
                ContextBindingSupport.bindingDigest(write));
    }
}
