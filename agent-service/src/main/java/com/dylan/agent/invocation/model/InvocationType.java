package com.dylan.agent.invocation.model;

/**
 * Invocation 类型：CHAT（单 Agent 对话）或 TASK（D06 Multi-Agent 子任务）。
 * D03 只创建 CHAT，TASK 由 D06 激活。
 */
public enum InvocationType { CHAT, TASK }
