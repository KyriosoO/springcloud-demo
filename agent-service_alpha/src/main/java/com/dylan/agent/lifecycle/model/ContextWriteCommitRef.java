package com.dylan.agent.lifecycle.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;

/**
 * Context Write Commit Ref — 不可变安全审计值，记录实际提交的 Context 写操作的
 * 标识和摘要。不含 payload、Owner/Scope 重复副本或密钥。
 *
 * <p>按照 D02_02 §3.3 设计。</p>
 */
public final class ContextWriteCommitRef {

    private final String contextId;
    private final RuntimeContextType contextType;
    private final ContractRef targetContract;
    private final int targetRecordVersion;
    private final String digest;

    public ContextWriteCommitRef(
            String contextId,
            RuntimeContextType contextType,
            ContractRef targetContract,
            int targetRecordVersion,
            String digest) {
        this.contextId = Objects.requireNonNull(contextId);
        this.contextType = Objects.requireNonNull(contextType);
        this.targetContract = Objects.requireNonNull(targetContract);
        this.targetRecordVersion = targetRecordVersion;
        this.digest = Objects.requireNonNull(digest);
        if (contextId.isBlank()) {
            throw new IllegalArgumentException("contextId must not be blank");
        }
        if (targetRecordVersion < 0) {
            throw new IllegalArgumentException("targetRecordVersion must be non-negative");
        }
        if (digest.isBlank()) {
            throw new IllegalArgumentException("digest must not be blank");
        }
    }

    public String contextId() { return contextId; }
    public RuntimeContextType contextType() { return contextType; }
    public ContractRef targetContract() { return targetContract; }
    public int targetRecordVersion() { return targetRecordVersion; }
    public String digest() { return digest; }
}
