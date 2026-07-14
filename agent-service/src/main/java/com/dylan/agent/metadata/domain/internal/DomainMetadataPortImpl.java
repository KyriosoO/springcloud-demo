package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainFieldSchema;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainRoutingProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainSchema;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.DomainExecutionResolution;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.CanonicalFunctionRef;
import com.dylan.agent.metadata.domain.port.CanonicalOperatorRef;
import com.dylan.agent.metadata.domain.port.DomainAdapterKey;
import com.dylan.agent.metadata.domain.port.DomainAvailabilitySnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;

import org.springframework.context.ApplicationContext;

import java.time.Clock;
import java.time.Instant;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** D02_03 DomainMetadataPort 边界的 D04 生产实现。 */
public final class DomainMetadataPortImpl implements DomainMetadataPort {

    private final DomainMetadataStore store;
    private final ApplicationContext applicationContext;
    private final AdapterAvailabilityResolver availabilityResolver;
    private final Clock clock;

    public DomainMetadataPortImpl(
            DomainMetadataStore store,
            ApplicationContext applicationContext,
            AdapterAvailabilityResolver availabilityResolver,
            Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.applicationContext = Objects.requireNonNull(applicationContext);
        this.availabilityResolver = Objects.requireNonNull(availabilityResolver);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public Set<AdapterRole> knownRoles() {
        DomainMetadataStaticBundle bundle = store.current();
        return java.util.stream.Stream.concat(
                        AdapterRolePortTypes.knownRoles().stream(),
                        bundle.registrations().roles().stream())
                .collect(Collectors.toUnmodifiableSet());
    }

    @Override
    public DomainMetadataEvidence validateReferences(
            DomainMetadataReferenceSet refs,
            Instant absoluteDeadline) {
        Objects.requireNonNull(refs, "refs must not be null");
        DomainMetadataStaticBundle bundle = store.current();
        checkDeadline(absoluteDeadline);
        for (String domain : refs.domains()) {
            bundle.catalog().requireDomain(domain);
        }
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
        return captureEvidence(bundle, Set.of(), absoluteDeadline).evidence();
    }

    @Override
    public DomainAvailabilitySnapshot availability(
            Set<AdapterRole> roles,
            PlanningEffectiveScope scope,
            Instant absoluteDeadline) {
        Objects.requireNonNull(roles, "roles must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        DomainMetadataStaticBundle bundle = store.current();
        Set<DomainAdapterKey> keys = roles.stream()
                .flatMap(role -> bundle.registrations().domains(role).stream()
                        .filter(domain -> bundle.catalog().supportsRole(domain, role))
                        .map(domain -> new DomainAdapterKey(role, domain)))
                .collect(Collectors.toUnmodifiableSet());
        CurrentView view = captureEvidence(bundle, keys, absoluteDeadline);
        Map<AdapterRole, Set<String>> result = new LinkedHashMap<>();
        for (AdapterRole role : roles) {
            Set<String> domains = bundle.registrations().domains(role).stream()
                    .filter(domain -> bundle.catalog().supportsRole(domain, role))
                    .filter(domain -> view.availability().isAvailable(new DomainAdapterKey(role, domain)))
                    .filter(scope.allowedDomains()::contains)
                    .collect(Collectors.toCollection(java.util.TreeSet::new));
            result.put(role, domains);
        }
        return new DomainAvailabilitySnapshot(view.evidence(), result);
    }

    @Override
    public void assertCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline) {
        requireCurrent(expected, absoluteDeadline);
    }

    @Override
    public List<RuntimeDomainRoutingProjection> routeProjection(
            Set<String> domains,
            PlanningEffectiveScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline) {
        CurrentView view = requireCurrent(expected, absoluteDeadline);
        Objects.requireNonNull(domains, "domains must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        return domains.stream()
                .filter(scope.allowedDomains()::contains)
                .filter(domain -> isAvailableForAnyEvaluatedRole(view, domain))
                .map(view.bundle().catalog()::requireDomain)
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
        CurrentView view = requireCurrent(expected, absoluteDeadline);
        Objects.requireNonNull(role, "role must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        requireAvailable(view, new DomainAdapterKey(role, domain));
        CanonicalDomainDefinition definition = view.bundle().catalog().requireDomain(domain);
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
        schema.setSortFields(capability.sortFields().stream()
                .filter(allowedFields::contains)
                .sorted()
                .toList());
        return schema;
    }

    @Override
    public DomainExecutionResolution resolveExecution(
            AdapterRole role,
            String domain,
            ExecutionScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline) {
        CurrentView view = requireCurrent(expected, absoluteDeadline);
        if (!scope.allowedDomains().contains(domain)) {
            throw new IllegalStateException("domain not allowed by execution scope: " + domain);
        }
        DomainAdapterKey selectedKey = new DomainAdapterKey(role, domain);
        requireAvailable(view, selectedKey);
        CanonicalDomainDefinition definition = view.bundle().catalog().requireDomain(domain);
        CanonicalRoleCapability capability = requireCapability(definition, role);
        Set<String> allowed = scope.allowedFields().getOrDefault(domain, Set.of());
        Map<String, ExecutionFieldRule> fieldRules = capability.fields().stream()
                .filter(allowed::contains)
                .sorted()
                .collect(Collectors.toMap(
                        field -> field,
                        field -> toExecutionFieldRule(domain, field, definition, capability, scope),
                        (left, right) -> left,
                        LinkedHashMap::new));
        List<String> defaultSelect = definition.defaultSelectFieldsByRole().getOrDefault(role, List.of()).stream()
                .filter(fieldRules::containsKey)
                .toList();
        Set<String> sortFields = capability.sortFields().stream()
                .filter(fieldRules::containsKey)
                .collect(Collectors.toUnmodifiableSet());
        ExecutionValidationProjection projection = new ExecutionValidationProjection(
                role,
                domain,
                fieldRules,
                defaultSelect,
                sortFields,
                expected.staticEvidence().safeRef());
        AdapterRegistration registration = view.bundle().registrations().require(role, domain);
        Class<? extends AgentAdapterPort> expectedType = AdapterRolePortTypes.requirePortType(role);
        AgentAdapterPort port = applicationContext.getBean(registration.portBeanName(), expectedType);
        AdapterExecutionBinding binding = new AdapterExecutionBinding(
                role,
                domain,
                expectedType,
                port,
                registration.registrationId(),
                registration.registrationVersion(),
                view.bundle().registrations().requireCapabilityRef(role, domain),
                expected,
                clock.instant());
        return new DomainExecutionResolution(binding, projection, expected);
    }

    private CurrentView captureEvidence(
            DomainMetadataStaticBundle bundle,
            Set<DomainAdapterKey> keys,
            Instant absoluteDeadline) {
        checkDeadline(absoluteDeadline);
        AdapterDeploymentAvailability availability = availabilityResolver.capture(keys, absoluteDeadline);
        if (!availability.entries().keySet().equals(keys)) {
            throw new IllegalStateException("availability resolver returned incomplete key set");
        }
        if (store.current() != bundle) {
            throw new IllegalStateException("domain metadata static bundle changed during capture");
        }
        DomainMetadataEvidence evidence = new DomainMetadataEvidence(
                bundle.staticEvidence(),
                keys,
                DomainMetadataEvidence.keysDigest(keys),
                availability.canonicalDigest(),
                availability.capturedAt());
        return new CurrentView(bundle, availability, evidence);
    }

    private CurrentView requireCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline) {
        Objects.requireNonNull(expected, "expected evidence must not be null");
        DomainMetadataStaticBundle bundle = store.current();
        if (!bundle.staticEvidence().equals(expected.staticEvidence())) {
            throw new IllegalStateException("domain metadata static evidence is stale");
        }
        CurrentView current = captureEvidence(bundle, expected.evaluatedKeys(), absoluteDeadline);
        if (!current.evidence().evaluatedKeysDigest().equals(expected.evaluatedKeysDigest())
                || !current.evidence().availabilityDigest().equals(expected.availabilityDigest())) {
            throw new IllegalStateException("domain metadata availability evidence is stale");
        }
        return current;
    }

    private static void requireAvailable(CurrentView view, DomainAdapterKey key) {
        if (!view.evidence().evaluatedKeys().contains(key) || !view.availability().isAvailable(key)) {
            throw new IllegalStateException("selected adapter is not currently available");
        }
    }

    private static boolean isAvailableForAnyEvaluatedRole(CurrentView view, String domain) {
        return view.evidence().evaluatedKeys().stream()
                .filter(key -> key.domain().equals(domain))
                .anyMatch(view.availability()::isAvailable);
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
            String domain,
            String field,
            CanonicalDomainDefinition definition,
            CanonicalRoleCapability capability,
            ExecutionScope scope) {
        CanonicalFieldDefinition fd = definition.fields().get(field);
        String fieldKey = domain + "." + field;
        return new ExecutionFieldRule(
                field,
                fd.type(),
                capability.operatorsByField().getOrDefault(field, Set.of()).stream()
                        .filter(scope.allowedOperators().getOrDefault(fieldKey, Set.of())::contains)
                        .collect(Collectors.toUnmodifiableSet()),
                capability.functionsByField().getOrDefault(field, Set.of()).stream()
                        .filter(function -> scope.allowedFunctions().getOrDefault(fieldKey, Set.of())
                                .contains(functionId(function)))
                        .collect(Collectors.toUnmodifiableSet()),
                fd.maxLength().orElse(null),
                fd.precision().orElse(null),
                fd.scale().orElse(null),
                fd.valueFormat().orElse(null));
    }

    private static CanonicalRoleCapability requireCapability(
            CanonicalDomainDefinition definition,
            AdapterRole role) {
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
            return AggregateFunction.valueOf(function.functionId().toUpperCase(java.util.Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("unknown function reference: " + function, ex);
        }
    }

    private static String functionId(AggregateFunction function) {
        return function.name().toLowerCase(java.util.Locale.ROOT);
    }

    private record CurrentView(
            DomainMetadataStaticBundle bundle,
            AdapterDeploymentAvailability availability,
            DomainMetadataEvidence evidence) {
    }
}
