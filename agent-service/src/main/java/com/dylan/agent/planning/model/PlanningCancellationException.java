package com.dylan.agent.planning.model;

import java.util.Objects;

/** Exception channel carrying only a typed PlanningCancellation value. */
public final class PlanningCancellationException extends RuntimeException {

    private final PlanningCancellation cancellation;

    public PlanningCancellationException(PlanningCancellation cancellation) {
        super(cancellation.errorCode().name());
        this.cancellation = Objects.requireNonNull(cancellation, "cancellation must not be null");
    }

    public PlanningCancellation cancellation() {
        return cancellation;
    }
}
