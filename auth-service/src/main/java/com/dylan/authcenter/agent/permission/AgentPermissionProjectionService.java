package com.dylan.authcenter.agent.permission;

import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;
import com.dylan.authcenter.agent.permission.api.SubjectRefDto;
import com.dylan.authcenter.config.AuthRbacProperties;
import com.dylan.authcenter.service.UserService;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

/**
 * 将 auth-service 内部用户授权事实转换为 Agent 可消费的 UserPermission 投影。
 *
 * <p>首版以 UserService 中的用户角色为内部输入，输出仍是完整权限投影；
 * 未来替换为数据库或权限规则引擎时，应保持本服务的请求/响应契约不变。</p>
 */
@Service
public class AgentPermissionProjectionService {

    static final String REQUIRED_SUBJECT_TYPE = "USER";
    private final UserService userService;
    private final AuthRbacProperties rbacProperties;
    private final Clock clock;

    @Autowired
    public AgentPermissionProjectionService(UserService userService, AuthRbacProperties rbacProperties) {
        this(userService, rbacProperties, Clock.systemUTC());
    }

    AgentPermissionProjectionService(
            UserService userService,
            AuthRbacProperties rbacProperties,
            Clock clock) {
        this.userService = userService;
        this.rbacProperties = rbacProperties;
        this.clock = clock;
    }

    public AgentPermissionResolveResponse resolve(AgentPermissionResolveRequest request) {
        validate(request);
        AuthRbacProperties.UserDefinition user = rbacProperties.getUsers().get(request.subject().id());
        if (user == null || isBlank(user.getTenantRef())) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_SUBJECT_NOT_FOUND);
        }
        Set<String> roles;
        try {
            roles = userService.rolesOf(request.subject().id());
        } catch (UsernameNotFoundException ex) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_SUBJECT_NOT_FOUND);
        }
        if (roles.isEmpty()) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_SUBJECT_NOT_FOUND);
        }
        Projection projection = projectionFor(roles);
        Instant resolvedAt = Instant.now(clock);
        Instant validUntil = resolvedAt.plus(rbacProperties.getPermissionFactTtl());
        if (request.deadline().isBefore(validUntil)) {
            validUntil = request.deadline();
        }
        if (!validUntil.isAfter(resolvedAt)) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_DEADLINE_EXCEEDED);
        }
        return new AgentPermissionResolveResponse(
                request.subject(),
                user.getTenantRef(),
                projection.permissionCodes(),
                evidenceId(request.subject(), user.getTenantRef(), projection),
                rbacProperties.getRuleVersion(),
                projection.allowedCapabilityIds(),
                projection.allowedDomains(),
                projection.filterableFields(),
                projection.displayableFields(),
                projection.allowedOperators(),
                projection.allowedFunctions(),
                projection.readableContextTypes(),
                projection.writableContextTypes(),
                projection.attributes(),
                resolvedAt,
                validUntil);
    }

    private void validate(AgentPermissionResolveRequest request) {
        if (request == null
                || isBlank(request.requestId())
                || request.subject() == null
                || isBlank(request.subject().type())
                || isBlank(request.subject().id())
                || request.requestedAt() == null
                || request.deadline() == null) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INVALID_REQUEST);
        }
        if (!REQUIRED_SUBJECT_TYPE.equals(request.subject().type())) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INVALID_REQUEST);
        }
        if (!request.deadline().isAfter(Instant.now(clock))) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_DEADLINE_EXCEEDED);
        }
    }

    private Projection projectionFor(Set<String> roles) {
        Projection projection = Projection.empty();
        for (String roleId : new TreeSet<>(roles)) {
            AuthRbacProperties.RoleDefinition role = rbacProperties.getRoles().get(roleId);
            if (role == null || isBlank(role.getPermissionProfile())) {
                continue;
            }
            AuthRbacProperties.PermissionProfile profile =
                    rbacProperties.getPermissionProfiles().get(role.getPermissionProfile());
            if (profile == null) {
                throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INTERNAL_ERROR);
            }
            projection = projection.merge(Projection.from(profile, role.getPermissionCodes()));
        }
        return projection;
    }

    private String evidenceId(SubjectRefDto subject, String tenantRef, Projection projection) {
        String canonical = subject.type() + "|" + subject.id() + "|" + tenantRef + "|"
                + rbacProperties.getRuleVersion() + "|" + projection.canonical();
        return "perm-" + subject.type().toLowerCase() + "-" + digest(canonical);
    }

    private static String digest(String canonical) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(canonical.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(bytes, 0, 8);
        } catch (NoSuchAlgorithmException ex) {
            throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INTERNAL_ERROR);
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private record Projection(
            Set<String> permissionCodes,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<String, Set<String>> filterableFields,
            Map<String, Set<String>> displayableFields,
            Map<String, Set<String>> allowedOperators,
            Map<String, Set<String>> allowedFunctions,
            Set<String> readableContextTypes,
            Set<String> writableContextTypes,
            Map<String, String> attributes) {

        static Projection empty() {
            return new Projection(
                    Set.of(), Set.of(), Set.of(), Map.of(), Map.of(), Map.of(), Map.of(), Set.of(), Set.of(), Map.of());
        }

        static Projection from(AuthRbacProperties.PermissionProfile profile, Set<String> permissionCodes) {
            return new Projection(
                    permissionCodes,
                    profile.getAllowedCapabilityIds(),
                    profile.getAllowedDomains(),
                    profile.getFilterableFields(),
                    profile.getDisplayableFields(),
                    profile.getAllowedOperators(),
                    profile.getAllowedFunctions(),
                    profile.getReadableContextTypes(),
                    profile.getWritableContextTypes(),
                    profile.getAttributes());
        }

        Projection merge(Projection other) {
            Map<String, String> mergedAttributes = new TreeMap<>(attributes);
            other.attributes.forEach((key, value) -> mergedAttributes.merge(
                    key, value, (left, right) -> left.equals(right) ? left : left + "+" + right));
            return new Projection(
                    union(permissionCodes, other.permissionCodes),
                    union(allowedCapabilityIds, other.allowedCapabilityIds),
                    union(allowedDomains, other.allowedDomains),
                    mergeMap(filterableFields, other.filterableFields),
                    mergeMap(displayableFields, other.displayableFields),
                    mergeMap(allowedOperators, other.allowedOperators),
                    mergeMap(allowedFunctions, other.allowedFunctions),
                    union(readableContextTypes, other.readableContextTypes),
                    union(writableContextTypes, other.writableContextTypes),
                    mergedAttributes);
        }

        Projection {
            permissionCodes = orderedSet(permissionCodes);
            allowedCapabilityIds = orderedSet(allowedCapabilityIds);
            allowedDomains = orderedSet(allowedDomains);
            filterableFields = orderedMap(filterableFields);
            displayableFields = orderedMap(displayableFields);
            allowedOperators = orderedMap(allowedOperators);
            allowedFunctions = orderedMap(allowedFunctions);
            readableContextTypes = orderedSet(readableContextTypes);
            writableContextTypes = orderedSet(writableContextTypes);
            attributes = new TreeMap<>(attributes == null ? Map.of() : attributes);
        }

        String canonical() {
            return permissionCodes + "|"
                    + allowedCapabilityIds + "|"
                    + allowedDomains + "|"
                    + filterableFields + "|"
                    + displayableFields + "|"
                    + allowedOperators + "|"
                    + allowedFunctions + "|"
                    + readableContextTypes + "|"
                    + writableContextTypes + "|"
                    + attributes;
        }

        private static Set<String> orderedSet(Set<String> values) {
            return values == null || values.isEmpty()
                    ? Set.of()
                    : new LinkedHashSet<>(new TreeSet<>(values));
        }

        private static Map<String, Set<String>> orderedMap(Map<String, Set<String>> values) {
            if (values == null || values.isEmpty()) {
                return Map.of();
            }
            Map<String, Set<String>> ordered = new LinkedHashMap<>();
            values.entrySet().stream()
                    .sorted(Map.Entry.comparingByKey())
                    .forEach(entry -> ordered.put(entry.getKey(), orderedSet(entry.getValue())));
            return ordered;
        }

        private static Set<String> union(Set<String> left, Set<String> right) {
            Set<String> merged = new LinkedHashSet<>(left);
            merged.addAll(right);
            return merged;
        }

        private static Map<String, Set<String>> mergeMap(
                Map<String, Set<String>> left,
                Map<String, Set<String>> right) {
            Map<String, Set<String>> merged = new LinkedHashMap<>();
            left.forEach((key, value) -> merged.put(key, new LinkedHashSet<>(value)));
            right.forEach((key, value) -> merged.computeIfAbsent(key, ignored -> new LinkedHashSet<>()).addAll(value));
            return merged;
        }
    }
}
