package com.dylan.authcenter.agent.permission;

import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;
import com.dylan.authcenter.agent.permission.api.SubjectRefDto;
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
import java.util.stream.Collectors;

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
    /**
     * 静态首版规则版本。任何权限规则或授权数据语义变化，都需要同步推进该版本。
     */
    static final String RULE_VERSION = "authz-20260702000000-1";

    private static final Set<String> STRING_OPERATORS = Set.of(
            "EQ", "CONTAINS", "CONTAINS_ANY", "STARTS_WITH", "STARTS_WITH_ANY", "IN");
    private static final Set<String> RANGE_OPERATORS = Set.of("EQ", "GT", "LT");
    private static final Set<String> AMOUNT_FUNCTIONS = Set.of("sum", "avg", "min", "max");
    private static final Set<String> EMPLOYEE_FIELDS = Set.of(
            "chineseName", "memberNo", "position", "contactAddress", "idCardNo", "phoneNo", "email");
    private static final Set<String> VIEWER_EMPLOYEE_FIELDS = Set.of("chineseName", "memberNo", "position");
    private static final Set<String> TRANSACTION_FIELDS = Set.of("transId", "transType", "transDate", "amount");

    private final UserService userService;
    private final Clock clock;

    @Autowired
    public AgentPermissionProjectionService(UserService userService) {
        this(userService, Clock.systemUTC());
    }

    AgentPermissionProjectionService(UserService userService, Clock clock) {
        this.userService = userService;
        this.clock = clock;
    }

    public AgentPermissionResolveResponse resolve(AgentPermissionResolveRequest request) {
        validate(request);
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
        // 请求参数只能缩小 auth-service 已授权范围，不能因请求方声明而扩大权限。
        Projection narrowed = projection.narrow(request.requestedCapabilityIds(), request.requestedDomains());
        Instant resolvedAt = Instant.now(clock);
        return new AgentPermissionResolveResponse(
                request.subject(),
                evidenceId(request.subject(), narrowed),
                RULE_VERSION,
                narrowed.allowedCapabilityIds(),
                narrowed.allowedDomains(),
                narrowed.filterableFields(),
                narrowed.displayableFields(),
                narrowed.allowedOperators(),
                narrowed.allowedFunctions(),
                narrowed.readableContextTypes(),
                narrowed.writableContextTypes(),
                narrowed.attributes(),
                resolvedAt);
    }

    private void validate(AgentPermissionResolveRequest request) {
        if (request == null
                || isBlank(request.requestId())
                || request.subject() == null
                || isBlank(request.subject().type())
                || isBlank(request.subject().id())
                || request.requestedAt() == null
                || request.deadline() == null
                || isBlank(request.agentId())
                || isBlank(request.profileId())
                || isBlank(request.scopeType())
                || isBlank(request.scopeId())) {
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
        if (roles.contains("agent:admin")) {
            return adminProjection();
        }
        if (roles.contains("agent:viewer")) {
            return viewerProjection();
        }
        return Projection.empty();
    }

    private Projection adminProjection() {
        Map<String, Set<String>> fields = new LinkedHashMap<>();
        fields.put("employee", EMPLOYEE_FIELDS);
        fields.put("transaction", TRANSACTION_FIELDS);

        Map<String, Set<String>> operators = new LinkedHashMap<>();
        addOperators(operators, "employee", EMPLOYEE_FIELDS, STRING_OPERATORS);
        operators.put("transaction.transId", Set.of("EQ"));
        operators.put("transaction.transType", Set.of("EQ", "CONTAINS"));
        operators.put("transaction.transDate", Set.of("GT", "LT"));
        operators.put("transaction.amount", RANGE_OPERATORS);

        return new Projection(
                Set.of("query.search", "aggregate.compute"),
                Set.of("employee", "transaction"),
                fields,
                fields,
                operators,
                Map.of("transaction.amount", AMOUNT_FUNCTIONS),
                Set.of("QUERY", "AGGREGATE"),
                Set.of("QUERY", "AGGREGATE"),
                Map.of("source", "auth-service-agent-permission", "policyTier", "admin"));
    }

    private Projection viewerProjection() {
        Map<String, Set<String>> fields = Map.of("employee", VIEWER_EMPLOYEE_FIELDS);
        Map<String, Set<String>> operators = new LinkedHashMap<>();
        addOperators(operators, "employee", VIEWER_EMPLOYEE_FIELDS, STRING_OPERATORS);
        return new Projection(
                Set.of("query.search"),
                Set.of("employee"),
                fields,
                fields,
                operators,
                Map.of(),
                Set.of("QUERY"),
                Set.of("QUERY"),
                Map.of("source", "auth-service-agent-permission", "policyTier", "viewer"));
    }

    private static void addOperators(
            Map<String, Set<String>> operators,
            String domain,
            Set<String> fields,
            Set<String> allowedOperators) {
        fields.forEach(field -> operators.put(domain + "." + field, allowedOperators));
    }

    private String evidenceId(SubjectRefDto subject, Projection projection) {
        String canonical = subject.type() + "|" + subject.id() + "|" + RULE_VERSION + "|" + projection.canonical();
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
                    Set.of(), Set.of(), Map.of(), Map.of(), Map.of(), Map.of(), Set.of(), Set.of(),
                    Map.of("source", "auth-service-agent-permission", "policyTier", "none"));
        }

        Projection {
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

        Projection narrow(Set<String> requestedCapabilityIds, Set<String> requestedDomains) {
            Set<String> capabilities = intersect(allowedCapabilityIds, requestedCapabilityIds);
            Set<String> domains = intersect(allowedDomains, requestedDomains);
            Map<String, Set<String>> filterable = restrictDomainMap(filterableFields, domains);
            Map<String, Set<String>> displayable = restrictDomainMap(displayableFields, domains);
            return new Projection(
                    capabilities,
                    domains,
                    filterable,
                    displayable,
                    restrictFieldMap(allowedOperators, domains),
                    capabilities.contains("aggregate.compute") ? restrictFieldMap(allowedFunctions, domains) : Map.of(),
                    readableContextTypes,
                    writableContextTypes,
                    attributes);
        }

        String canonical() {
            return allowedCapabilityIds + "|"
                    + allowedDomains + "|"
                    + filterableFields + "|"
                    + displayableFields + "|"
                    + allowedOperators + "|"
                    + allowedFunctions + "|"
                    + readableContextTypes + "|"
                    + writableContextTypes + "|"
                    + attributes;
        }

        private static Set<String> intersect(Set<String> source, Set<String> requested) {
            if (requested == null || requested.isEmpty()) {
                return source;
            }
            return source.stream()
                    .filter(requested::contains)
                    .collect(Collectors.toCollection(LinkedHashSet::new));
        }

        private static Map<String, Set<String>> restrictDomainMap(
                Map<String, Set<String>> source,
                Set<String> allowedDomains) {
            return source.entrySet().stream()
                    .filter(entry -> allowedDomains.contains(entry.getKey()))
                    .collect(Collectors.toMap(
                            Map.Entry::getKey,
                            Map.Entry::getValue,
                            (left, right) -> left,
                            LinkedHashMap::new));
        }

        private static Map<String, Set<String>> restrictFieldMap(
                Map<String, Set<String>> source,
                Set<String> allowedDomains) {
            return source.entrySet().stream()
                    .filter(entry -> allowedDomains.contains(domainOf(entry.getKey())))
                    .collect(Collectors.toMap(
                            Map.Entry::getKey,
                            Map.Entry::getValue,
                            (left, right) -> left,
                            LinkedHashMap::new));
        }

        private static String domainOf(String fieldKey) {
            int dotIndex = fieldKey.indexOf('.');
            return dotIndex < 0 ? fieldKey : fieldKey.substring(0, dotIndex);
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
    }
}
