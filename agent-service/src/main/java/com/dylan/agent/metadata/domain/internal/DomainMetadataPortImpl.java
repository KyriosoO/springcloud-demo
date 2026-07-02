package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainFieldSchema;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainRoutingProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainSchema;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.CanonicalFunctionRef;
import com.dylan.agent.metadata.domain.port.CanonicalOperatorRef;
import com.dylan.agent.metadata.domain.port.DomainAvailabilitySnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;

import java.time.Clock;
import java.time.Instant;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.context.ApplicationContext;

/** D02_03 DomainMetadataPort 边界的 D04 生产实现。 */
public final class DomainMetadataPortImpl implements DomainMetadataPort {

    private final DomainMetadataStore store;
    private final ApplicationContext applicationContext;
    private final Clock clock;

    public DomainMetadataPortImpl(
            DomainMetadataStore store,
            ApplicationContext applicationContext,
            Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.applicationContext = Objects.requireNonNull(applicationContext);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public Set<AdapterRole> knownRoles() {
        DomainMetadataBundle bundle = store.current();
        return java.util.stream.Stream.concat(
                        AdapterRolePortTypes.knownRoles().stream(),
                        bundle.registrations().roles().stream())
                .collect(Collectors.toUnmodifiableSet());
    }

    @Override
    public DomainMetadataEvidence validateReferences(
            DomainMetadataReferenceSet refs,
            Instant absoluteDeadline) {
        checkDeadline(absoluteDeadline);
        DomainMetadataBundle bundle = store.current();
        for (CanonicalFieldRef field : refs.fields()) {
            if (!bundle.catalog().requireDomain(field.domain()).fields().containsKey(field.field())) {
                throw new IllegalStateException("unknown field reference: " + field);
            }
        }
        for (CanonicalOperatorRef operator : refs.operators()) {
            CanonicalFieldRef field = operator.fieldRef();
            boolean supported = bundle.catalog().requireDomain(field.domain()).roleCapabilities().values().stream()
                    .anyMatch(capability -> capability.operatorsByField()
                            .getOrDefault(field.field(), Set.of()).contains(operator.operator()));
            if (!supported) {
                throw new IllegalStateException("unknown operator reference: " + operator);
            }
        }
        for (CanonicalFunctionRef function : refs.functions()) {
            CanonicalFieldRef field = function.fieldRef();
            AggregateFunction aggregateFunction = parseFunction(function);
            boolean supported = bundle.catalog().requireDomain(field.domain()).roleCapabilities().values().stream()
                    .anyMatch(capability -> capability.functionsByField()
                            .getOrDefault(field.field(), Set.of()).contains(aggregateFunction));
            if (!supported) {
                throw new IllegalStateException("unknown function reference: " + function);
            }
        }
        return bundle.evidence();
    }

    @Override
    public DomainAvailabilitySnapshot availability(
            Set<AdapterRole> roles,
            PlanningEffectiveScope scope,
            Instant absoluteDeadline) {
        checkDeadline(absoluteDeadline);
        Objects.requireNonNull(roles, "roles must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        DomainMetadataBundle bundle = store.current();
        Map<AdapterRole, Set<String>> result = new LinkedHashMap<>();
        for (AdapterRole role : roles) {
            Set<String> domains = bundle.registrations().domains(role).stream()
                    .filter(domain -> bundle.catalog().supportsRole(domain, role))
                    .filter(domain -> bundle.availability().isAvailable(role, domain))
                    .filter(domain -> scope.allowedDomains().contains(domain))
                    .collect(Collectors.toCollection(java.util.TreeSet::new));
            result.put(role, domains);
        }
        return new DomainAvailabilitySnapshot(bundle.evidence(), result);
    }

    @Override
    public void assertCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline) {
        checkDeadline(absoluteDeadline);
        if (!store.current().evidence().equals(expected)) {
            throw new IllegalStateException("domain metadata evidence is stale");
        }
    }

    @Override
    public List<RuntimeDomainRoutingProjection> routeProjection(
            Set<String> domains,
            PlanningEffectiveScope scope,
            DomainMetadataEvidence expected,
            String authorizationEvidenceDigest,
            Instant absoluteDeadline) {
        assertCurrent(expected, absoluteDeadline);
        Objects.requireNonNull(scope, "scope must not be null");
        DomainMetadataBundle bundle = store.current();
        return domains.stream()
                .filter(scope.allowedDomains()::contains)
                .map(bundle.catalog()::requireDomain)
                .sorted(Comparator.comparing(CanonicalDomainDefinition::domain))
                .map(domain -> {
                    RuntimeDomainRoutingProjection projection = new RuntimeDomainRoutingProjection();
                    projection.setDomain(domain.domain());
                    projection.setAliases(domain.aliases());
                    projection.setDescription(domain.description());
                    return projection;
                })
                .toList();
    }

    @Override
    public RuntimeDomainSchema planSchema(
            AdapterRole role,
            String domain,
            PlanningEffectiveScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline) {
        assertCurrent(expected, absoluteDeadline);
        Objects.requireNonNull(role, "role must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        CanonicalDomainDefinition definition = store.current().catalog().requireDomain(domain);
        CanonicalRoleCapability capability = requireCapability(definition, role);
        List<RuntimeDomainFieldSchema> fields = capability.fields().stream()
                .filter(field -> scope.fieldAccess().containsKey(new CanonicalFieldRef(domain, field)))
                .sorted()
                .map(field -> toRuntimeFieldSchema(domain, field, definition, capability, scope))
                .toList();
        Set<String> allowedFields = fields.stream()
                .map(RuntimeDomainFieldSchema::getField)
                .collect(Collectors.toUnmodifiableSet());
        RuntimeDomainSchema schema = new RuntimeDomainSchema();
        schema.setDomain(definition.domain());
        schema.setFields(fields);
        schema.setDefaultSelectFields(definition.defaultSelectFieldsByRole()
                .getOrDefault(role, List.of()).stream()
                .filter(allowedFields::contains)
                .toList());
        int roleMax = role.equals(AdapterRole.QUERYABLE) ? capability.maxPageSize() : capability.maxResultRows();
        int scopeMax = role.equals(AdapterRole.QUERYABLE) ? scope.maxPageSize() : scope.maxResultRows();
        schema.setMaxSize(positiveMin(roleMax, scopeMax));
        schema.setDefaultSize(schema.getMaxSize());
        return schema;
    }

    @Override
    public ExecutionValidationProjection executionProjection(
            AdapterRole role,
            String domain,
            ExecutionScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline) {
        assertCurrent(expected, absoluteDeadline);
        if (!scope.allowedDomains().contains(domain)) {
            throw new IllegalStateException("domain not allowed by execution scope: " + domain);
        }
        CanonicalDomainDefinition definition = store.current().catalog().requireDomain(domain);
        CanonicalRoleCapability capability = requireCapability(definition, role);
        Set<String> allowed = scope.allowedFields().getOrDefault(domain, Set.of());
        Map<String, ExecutionFieldRule> fieldRules = capability.fields().stream()
                .filter(allowed::contains)
                .sorted()
                .collect(Collectors.toMap(
                        field -> field,
                        field -> toExecutionFieldRule(field, definition, capability),
                        (left, right) -> left,
                        LinkedHashMap::new));
        List<String> defaultSelect = definition.defaultSelectFieldsByRole().getOrDefault(role, List.of()).stream()
                .filter(fieldRules::containsKey)
                .toList();
        return new ExecutionValidationProjection(
                role,
                domain,
                fieldRules,
                defaultSelect,
                positiveMin(capability.maxPageSize(), scope.maxResultRows()),
                positiveMin(capability.maxResultRows(), scope.maxResultRows()),
                expected.catalogVersion() + ":" + expected.adapterRegistrationVersion());
    }

    @Override
    public AdapterExecutionBinding bind(
            AdapterRole role,
            String domain,
            ExecutionScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline) {
        assertCurrent(expected, absoluteDeadline);
        if (!scope.allowedDomains().contains(domain)) {
            throw new IllegalStateException("domain not allowed by execution scope: " + domain);
        }
        AdapterRegistration registration = store.current().registrations().require(role, domain);
        Class<? extends AgentAdapterPort> expectedType = AdapterRolePortTypes.requirePortType(role);
        if (!expectedType.equals(registration.portType())) {
            throw new IllegalStateException("adapter registration port type mismatch");
        }
        AgentAdapterPort port = applicationContext.getBean(registration.portBeanName(), registration.portType());
        return new AdapterExecutionBinding(
                role,
                domain,
                registration.portType(),
                port,
                registration.registrationVersion(),
                clock.instant());
    }

    private RuntimeDomainFieldSchema toRuntimeFieldSchema(
            String domain,
            String field,
            CanonicalDomainDefinition definition,
            CanonicalRoleCapability capability,
            PlanningEffectiveScope scope) {
        CanonicalFieldDefinition fd = definition.fields().get(field);
        PlanningEffectiveScope.FieldAccess access = scope.fieldAccess().get(new CanonicalFieldRef(domain, field));
        RuntimeDomainFieldSchema schema = new RuntimeDomainFieldSchema();
        schema.setField(field);
        schema.setAliases(fd.aliases());
        schema.setType(fd.type());
        schema.setOperators(capability.operatorsByField().getOrDefault(field, Set.of()).stream()
                .filter(access.allowedOperators()::contains)
                .sorted(Comparator.comparing(Enum::name))
                .toList());
        schema.setAggregateFunctions(capability.functionsByField().getOrDefault(field, Set.of()).stream()
                .filter(function -> access.allowedFunctions().contains(functionId(function)))
                .sorted(Comparator.comparing(Enum::name))
                .toList());
        schema.setFormatHint(fd.valueFormat().orElse(null));
        return schema;
    }

    private ExecutionFieldRule toExecutionFieldRule(
            String field,
            CanonicalDomainDefinition definition,
            CanonicalRoleCapability capability) {
        CanonicalFieldDefinition fd = definition.fields().get(field);
        return new ExecutionFieldRule(
                field,
                fd.type(),
                capability.operatorsByField().getOrDefault(field, Set.of()),
                capability.functionsByField().getOrDefault(field, Set.of()),
                fd.maxLength().orElse(null),
                fd.precision().orElse(null),
                fd.scale().orElse(null),
                fd.valueFormat().orElse(null));
    }

    private CanonicalRoleCapability requireCapability(CanonicalDomainDefinition definition, AdapterRole role) {
        CanonicalRoleCapability capability = definition.roleCapabilities().get(role);
        if (capability == null) {
            throw new IllegalStateException("domain does not support role: " + definition.domain() + "/" + role);
        }
        return capability;
    }

    private void checkDeadline(Instant deadline) {
        Objects.requireNonNull(deadline, "deadline must not be null");
        if (!clock.instant().isBefore(deadline)) {
            throw new IllegalStateException("domain metadata deadline exceeded");
        }
    }

    private static AggregateFunction parseFunction(CanonicalFunctionRef function) {
        if (!function.functionId().matches("[a-z][a-z0-9_]{0,63}")) {
            throw new IllegalStateException("unknown function reference: " + function);
        }
        try {
            return AggregateFunction.valueOf(function.functionId().toUpperCase());
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("unknown function reference: " + function, ex);
        }
    }

    private static String functionId(AggregateFunction function) {
        return function.name().toLowerCase(java.util.Locale.ROOT);
    }

    private static int positiveMin(int left, int right) {
        if (left <= 0) {
            return Math.max(right, 0);
        }
        if (right <= 0) {
            return left;
        }
        return Math.min(left, right);
    }
}
