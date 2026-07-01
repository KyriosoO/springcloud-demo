package com.dylan.agent.lifecycle.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentResultPayload;

import java.util.Objects;
import java.util.Optional;

/**
 * Filtered and safe result materialized from the authoritative invocation result row.
 *
 * <p>This is only used to rebuild the current Agent API response after
 * finalization, CAS loser or commit-unknown reread. It is not a Multi-Agent
 * ResultRef and must not be propagated as a task dependency.</p>
 */
public final class StoredInvocationResult {

    private final String resultId;
    private final Optional<ContractRef> outputContract;
    private final Optional<AgentResultPayload> payload;
    private final String safeMessage;
    private final String safeSummary;

    public StoredInvocationResult(String resultId,
                                  ContractRef outputContract,
                                  AgentResultPayload payload,
                                  String safeMessage,
                                  String safeSummary) {
        this.resultId = requireNonBlank(resultId, "resultId");
        if ((outputContract == null) != (payload == null)) {
            throw new IllegalArgumentException("outputContract and payload must appear together");
        }
        this.outputContract = Optional.ofNullable(outputContract);
        this.payload = Optional.ofNullable(payload);
        this.safeMessage = requireNonBlank(safeMessage, "safeMessage");
        this.safeSummary = requireNonBlank(safeSummary, "safeSummary");
    }

    public String resultId() { return resultId; }
    public Optional<ContractRef> outputContract() { return outputContract; }
    public Optional<AgentResultPayload> payload() { return payload; }
    public String safeMessage() { return safeMessage; }
    public String safeSummary() { return safeSummary; }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
