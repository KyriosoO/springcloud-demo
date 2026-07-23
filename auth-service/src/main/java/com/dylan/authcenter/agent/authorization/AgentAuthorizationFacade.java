package com.dylan.authcenter.agent.authorization;

import java.time.Instant;

import org.springframework.stereotype.Service;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;

import com.dylan.authcenter.agent.authorization.api.AgentAuthorizationResolveRequest;
import com.dylan.authcenter.agent.authorization.api.AgentAuthorizationResolveResponse;
import com.dylan.authcenter.agent.authorization.api.AuthUpperBoundDto;
import com.dylan.authcenter.agent.authorization.api.TrustedIdentityDto;
import com.dylan.authcenter.agent.permission.AgentPermissionErrorCode;
import com.dylan.authcenter.agent.permission.AgentPermissionException;
import com.dylan.authcenter.agent.permission.AgentPermissionProjectionService;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;

@Service
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class AgentAuthorizationFacade {

	private final AgentUserTokenVerificationService tokenVerifier;
	private final AgentPermissionProjectionService projectionService;

	public AgentAuthorizationFacade(AgentUserTokenVerificationService tokenVerifier,
			AgentPermissionProjectionService projectionService) {
		this.tokenVerifier = tokenVerifier;
		this.projectionService = projectionService;
	}

	public AgentAuthorizationResolveResponse resolve(AgentAuthorizationResolveRequest request) {
		if (request == null || request.requestId() == null || request.requestId().isBlank()
				|| request.requestedAt() == null || request.deadline() == null
				|| !request.deadline().isAfter(Instant.now())) {
			throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INVALID_REQUEST);
		}
		VerifiedUserIdentity identity = tokenVerifier.verify(request.userBearerToken());
		AgentPermissionResolveResponse permission = projectionService.resolve(new AgentPermissionResolveRequest(
				request.requestId(), identity.subject(), request.requestedAt(), request.deadline()));
		if (!identity.tenantRef().equals(permission.tenantRef())) {
			throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INTERNAL_ERROR);
		}
		Instant validUntil = min(identity.validUntil(), permission.validUntil());
		return new AgentAuthorizationResolveResponse(
				new TrustedIdentityDto(identity.subject(), identity.tenantRef(),
						"user-jwt:" + identity.subject().id(), validUntil),
				new AuthUpperBoundDto(permission.permissionCodes(), permission.allowedCapabilityIds(),
						permission.allowedDomains(), permission.filterableFields(), permission.displayableFields(),
						permission.allowedOperators(), permission.allowedFunctions(), permission.evidenceId()),
				permission.resolvedAt(), validUntil);
	}

	private static Instant min(Instant left, Instant right) {
		return left.isBefore(right) ? left : right;
	}
}
