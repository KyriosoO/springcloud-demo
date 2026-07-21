package com.dylan.agent.lifecycle;

import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.Instant;
import java.util.Objects;

/**
 * 对超时 PROCESSING 调用执行有界恢复。
 */
@Service
public class InvocationRecoveryService {

    static final int MAX_BATCH_SIZE = 1000;

    private final AgentInvocationRecordMapper invocationMapper;
    private final AgentTurnMapper turnMapper;
    private final Clock clock;

    public InvocationRecoveryService(AgentInvocationRecordMapper invocationMapper,
                                     AgentTurnMapper turnMapper,
                                     Clock clock) {
        this.invocationMapper = Objects.requireNonNull(invocationMapper);
        this.turnMapper = Objects.requireNonNull(turnMapper);
        this.clock = Objects.requireNonNull(clock);
    }

    @Transactional
    public int recoverExpiredProcessing(Instant now, int batchSize) {
        Objects.requireNonNull(now, "now must not be null");
        if (batchSize <= 0 || batchSize > MAX_BATCH_SIZE) {
            throw new IllegalArgumentException(
                    "batchSize must be between 1 and " + MAX_BATCH_SIZE);
        }
        LocalDateTime cutoff = LocalDateTime.ofInstant(now, clock.getZone());
        LocalDateTime completedAt = LocalDateTime.now(clock);
        int recovered = 0;
        for (var record : invocationMapper.selectExpiredProcessing(cutoff, batchSize)) {
            int updated = invocationMapper.finalizeTerminal(
                    record.getId(),
                    "CANCELLED",
                    "CANCELLED",
                    "DEADLINE_EXCEEDED",
                    "请求已超时。",
                    "recovery-deadline",
                    completedAt,
                    record.getRowVersion());
            if (updated == 0) {
                continue;
            }
            if (turnMapper.finalizeFailure(
                    record.getTurnId(),
                    record.getId(),
                    "DEADLINE_EXCEEDED",
                    "请求已超时。",
                    completedAt) != 1) {
                throw new IllegalStateException("recover turn CAS failed: " + record.getTurnId());
            }
            recovered++;
        }
        return recovered;
    }
}
