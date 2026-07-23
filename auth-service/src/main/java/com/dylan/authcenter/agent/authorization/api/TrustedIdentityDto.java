package com.dylan.authcenter.agent.authorization.api;

import java.time.Instant;

import com.dylan.authcenter.agent.permission.api.SubjectRefDto;

public record TrustedIdentityDto(
		SubjectRefDto subject,
		String tenantRef,
		String identityEvidenceVersion,
		Instant validUntil) {
}
