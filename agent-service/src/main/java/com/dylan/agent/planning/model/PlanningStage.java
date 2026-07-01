package com.dylan.agent.planning.model;

/**
 * Internal Planning failure/cancellation stage.
 *
 * <p>This is not an invocation terminal state and is not exposed as an API response enum.</p>
 */
public enum PlanningStage {
    HISTORY,
    PROFILE_POLICY,
    CATALOG,
    ROUTE,
    REGISTRATION,
    CONTEXT,
    PLAN,
    SNAPSHOT_FREEZE
}
