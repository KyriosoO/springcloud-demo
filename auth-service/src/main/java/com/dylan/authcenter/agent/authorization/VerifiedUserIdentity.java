package com.dylan.authcenter.agent.authorization;

import java.time.Instant;

import com.dylan.authcenter.agent.permission.api.SubjectRefDto;

public record VerifiedUserIdentity(SubjectRefDto subject, String tenantRef, Instant validUntil) {
}
