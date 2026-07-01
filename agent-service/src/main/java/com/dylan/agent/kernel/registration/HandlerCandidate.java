package com.dylan.agent.kernel.registration;

import java.util.Objects;

/**
 * Handler 执行后的候选输出。
 */
public final class HandlerCandidate {

    private final Object output;

    public HandlerCandidate(Object output) {
        this.output = output;
    }

    public Object output() { return output; }
}
