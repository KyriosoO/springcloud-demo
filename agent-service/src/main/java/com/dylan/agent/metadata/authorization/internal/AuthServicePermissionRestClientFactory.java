package com.dylan.agent.metadata.authorization.internal;

import java.time.Duration;

import org.springframework.web.client.RestClient;

/** 为单次权限解析创建受 Invocation 剩余 deadline 约束的 HTTP client。 */
@FunctionalInterface
interface AuthServicePermissionRestClientFactory {
    RestClient create(Duration readTimeout);
}
