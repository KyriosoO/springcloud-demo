package com.dylan.agent.planning.model;

/** Route/Plan runtime operation 的安全终止类别。 */
public enum PlanningOperationTermination {
    OUTCOME_RECEIVED,
    RUNTIME_ERROR_RECEIVED,
    TRANSPORT_FAILURE,
    PROTOCOL_REJECTED,
    DEADLINE_EXCEEDED,
    CANCELLED
}
