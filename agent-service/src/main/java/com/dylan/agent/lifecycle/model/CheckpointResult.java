package com.dylan.agent.lifecycle.model;

/**
 * Planning checkpoint CAS 结果。
 */
public enum CheckpointResult {
    COMMITTED,
    TERMINAL_EXISTS,
    UNCOMMITTED,
    COMMIT_UNKNOWN
}
