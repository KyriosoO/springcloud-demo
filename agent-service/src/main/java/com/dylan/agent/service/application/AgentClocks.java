package com.dylan.agent.service.application;

public interface AgentClocks {
    long monotonicNanos();

    long epochMillis();
}
