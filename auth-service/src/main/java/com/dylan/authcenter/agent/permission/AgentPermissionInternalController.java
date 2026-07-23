package com.dylan.authcenter.agent.permission;

import com.dylan.authcenter.agent.permission.api.AgentPermissionErrorResponse;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;
import com.dylan.authcenter.agent.authorization.AgentAuthorizationFacade;
import com.dylan.authcenter.agent.authorization.api.AgentAuthorizationResolveRequest;
import com.dylan.common.security.SecurityTokenUtils;

import java.util.Set;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;

/**
 * agent-service 专用的内部权限投影入口。
 *
 * <p>该 Controller 只接受服务 token，不接受用户 JWT 或前端 cookie 作为权限事实。</p>
 */
@RestController
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class AgentPermissionInternalController {

    static final String REQUIRED_SERVICE = "agent-service";
    static final String REQUIRED_SCOPE = "agent.permission.resolve";

    private final AgentPermissionProjectionService projectionService;
    private final AgentAuthorizationFacade authorizationFacade;

    @Autowired
    public AgentPermissionInternalController(AgentPermissionProjectionService projectionService,
            AgentAuthorizationFacade authorizationFacade) {
        this.projectionService = projectionService;
        this.authorizationFacade = authorizationFacade;
    }

    AgentPermissionInternalController(AgentPermissionProjectionService projectionService) {
        this(projectionService, null);
    }

    @PostMapping("/internal/agent/authorization/resolve")
    public ResponseEntity<?> resolveAuthorization(
            @AuthenticationPrincipal Jwt jwt,
            @RequestBody AgentAuthorizationResolveRequest request) {
        if (!isAuthorizedService(jwt)) {
            return error(AgentPermissionErrorCode.AGENT_PERMISSION_UNAVAILABLE,
                    request == null ? "" : request.requestId(), HttpStatus.FORBIDDEN);
        }
        try {
            if (authorizationFacade == null) {
                throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INTERNAL_ERROR);
            }
            return ResponseEntity.ok(authorizationFacade.resolve(request));
        } catch (AgentPermissionException ex) {
            return error(ex.code(), request == null ? "" : request.requestId(), ex.code().status());
        }
    }

    @PostMapping("/internal/agent/permissions/resolve")
    public ResponseEntity<?> resolve(
            @AuthenticationPrincipal Jwt jwt,
            @RequestBody AgentPermissionResolveRequest request) {
        // 内部接口鉴权失败必须 fail closed，由 Adapter 统一映射为权限源不可用。
        if (!isAuthorizedService(jwt)) {
            return error(AgentPermissionErrorCode.AGENT_PERMISSION_UNAVAILABLE, request, HttpStatus.FORBIDDEN);
        }
        try {
            AgentPermissionResolveResponse response = projectionService.resolve(request);
            return ResponseEntity.ok(response);
        } catch (AgentPermissionException ex) {
            return error(ex.code(), request, ex.code().status());
        }
    }

    private ResponseEntity<AgentPermissionErrorResponse> error(
            AgentPermissionErrorCode code,
            AgentPermissionResolveRequest request,
            HttpStatus status) {
        return error(code, request == null ? "" : request.requestId(), status);
    }

    private ResponseEntity<AgentPermissionErrorResponse> error(
            AgentPermissionErrorCode code,
            String requestId,
            HttpStatus status) {
        return ResponseEntity.status(status)
                .body(new AgentPermissionErrorResponse(
                        requestId,
                        code.name(),
                        code.message(),
                        "aperm-" + UUID.randomUUID()));
    }

    private boolean isAuthorizedService(Jwt jwt) {
        return SecurityTokenUtils.isServiceToken(jwt)
                && REQUIRED_SERVICE.equals(SecurityTokenUtils.subject(jwt))
                && scopes(jwt).contains(REQUIRED_SCOPE);
    }

    private static Set<String> scopes(Jwt jwt) {
        String scope = jwt == null ? null : jwt.getClaimAsString("scope");
        if (scope == null || scope.isBlank()) {
            return Set.of();
        }
        return Set.of(scope.trim().split("\\s+"));
    }
}
