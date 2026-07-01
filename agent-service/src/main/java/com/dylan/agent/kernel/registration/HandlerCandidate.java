package com.dylan.agent.kernel.registration;

import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.util.List;
import java.util.Objects;

/**
 * Handler 执行后的候选输出。
 */
public final class HandlerCandidate {

    private final Object output;
    private final List<ContextWriteCandidate> contextWrites;

    public HandlerCandidate(Object output, List<ContextWriteCandidate> contextWrites) {
        this.output = Objects.requireNonNull(output);
        this.contextWrites = List.copyOf(contextWrites == null ? List.of() : contextWrites);
    }

    public Object output() { return output; }
    public List<ContextWriteCandidate> contextWrites() { return contextWrites; }
}
