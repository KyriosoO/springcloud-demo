package com.dylan.authcenter.agent.authorization.api;

import java.time.Instant;

public record AgentAuthorizationResolveResponse(
		TrustedIdentityDto trustedIdentity,
		AuthUpperBoundDto authUpperBound,
		Instant resolvedAt,
		Instant validUntil) {
}
