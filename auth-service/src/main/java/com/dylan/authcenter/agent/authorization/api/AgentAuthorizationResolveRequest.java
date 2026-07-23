package com.dylan.authcenter.agent.authorization.api;

import java.time.Instant;

public record AgentAuthorizationResolveRequest(
		String requestId,
		SensitiveBearerToken userBearerToken,
		Instant requestedAt,
		Instant deadline) {
}
