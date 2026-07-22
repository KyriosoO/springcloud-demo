package com.dylan.baseline.agent.security.authorization.internal;

import java.time.Duration;
import org.springframework.web.client.RestClient;

@FunctionalInterface
interface AuthPermissionRestClientFactory {

    RestClient create(Duration readTimeout);
}
