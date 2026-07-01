package com.dylan.agent.planning.model;

/** Safe termination categories for Route/Plan runtime operations. */
public enum PlanningOperationTermination {
    OUTCOME_RECEIVED,
    RUNTIME_ERROR_RECEIVED,
    TRANSPORT_FAILURE,
    PROTOCOL_REJECTED,
    DEADLINE_EXCEEDED,
    CANCELLED
}
