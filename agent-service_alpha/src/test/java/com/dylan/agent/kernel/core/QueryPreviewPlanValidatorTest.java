package com.dylan.agent.kernel.core;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.AgentSortSpec;
import com.dylan.agent.capability.querypreview.QueryPreviewPlanValidator;
import com.dylan.agent.capability.querypreview.ValidatedQueryPreviewPlan;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

class QueryPreviewPlanValidatorTest {

    private static final Instant NOW = Instant.parse("2026-07-02T00:00:00Z");

    @Test
    void validatesPreviewAgainstQueryableProjection() {
        var plan = validator().validate(queryPlan(List.of("name", "memberNo"), 3), context());

        assertThat(plan.capabilityId()).isEqualTo("query.preview");
        assertThat(plan.planKind()).isEqualTo(AgentPlanKind.QUERY);
        assertThat(plan.domain()).contains("employee");
        assertThat(plan.previewFields()).containsExactly("name", "memberNo");
        assertThat(plan.query().getPage()).isEqualTo(1);
        assertThat(plan.query().getSize()).isEqualTo(3);
    }

    @Test
    void defaultsPreviewFieldsAndSizeFromProjectionAndBudgets() {
        var plan = validator().validate(queryPlan(List.of(), null), context());

        assertThat(plan.previewFields()).containsExactly("name");
        assertThat(plan.previewSize()).isEqualTo(5);
    }

    @Test
    void rejectsUnauthorizedPreviewField() {
        assertThatThrownBy(() -> validator().validate(queryPlan(List.of("idCardNo"), 1), context()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("unknown field");
    }

    @Test
    void rejectsCapabilityIdMismatch() {
        assertThatThrownBy(() -> validator().validate(queryPlan(List.of("name"), 1), context("query.search")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("capabilityId mismatch");
    }

    @Test
    void rejectsUnauthorizedOperator() {
        QueryAgentPlan plan = queryPlan(List.of("name"), 1);
        plan.getQuery().getFilters().get(0).setOperator(AgentOperator.CONTAINS);

        assertThatThrownBy(() -> validator().validate(plan, context()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("operator not allowed");
    }

    @Test
    void rejectsPreviewSizeAboveEffectiveResourceLimit() {
        assertThatThrownBy(() -> validator().validate(queryPlan(List.of("name"), 6), context()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("invalid query preview size");
    }

    @Test
    void rejectsPreviewSizeAboveConfiguredDefaultEvenWhenOtherBudgetsAreHigher() {
        assertThatThrownBy(() -> validator().validate(queryPlan(List.of("name"), 21), contextWithMaxRows(100)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("invalid query preview size");
    }

    @Test
    void rejectsNonFirstPagePreview() {
        QueryAgentPlan plan = queryPlan(List.of("name"), 1);
        plan.getQuery().setPage(2);

        assertThatThrownBy(() -> validator().validate(plan, context()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("first page");
    }

    @Test
    void acceptsExplicitWhitelistedSorts() {
        QueryAgentPlan plan = queryPlan(List.of("name"), 1);
        plan.getQuery().setSorts(List.of(sort("memberNo", "desc")));

        var result = validator().validate(plan, contextWithSortFields(Set.of("memberNo")));

        assertThat(result.query().getSorts()).singleElement().satisfies(sort -> {
            assertThat(sort.getField()).isEqualTo("memberNo");
            assertThat(sort.getDirection()).isEqualTo("DESC");
        });
    }

    @Test
    void rejectsExplicitSortOutsideWhitelist() {
        QueryAgentPlan plan = queryPlan(List.of("name"), 1);
        plan.getQuery().setSorts(List.of(sort("memberNo", "ASC")));

        assertThatThrownBy(() -> validator().validate(plan, contextWithSortFields(Set.of())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("sort field is not allowed");
    }

    @Test
    void rejectsInconsistentValidatedPreviewPlan() {
        ValidatedQuery query = new ValidatedQuery(
                List.of(new ValidatedFilter("name", AgentOperator.EQ, "Alice", List.of())),
                List.of("name"),
                1,
                2);

        assertThatThrownBy(() -> new ValidatedQueryPreviewPlan(
                QueryPreviewPlanValidator.KERNEL_CAPABILITY_ID,
                "employee",
                query,
                List.of("memberNo"),
                2))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("previewFields");
    }

    private QueryPreviewPlanValidator validator() {
        AgentProperties properties = new AgentProperties();
        AgentProperties.QueryProperties query = new AgentProperties.QueryProperties();
        query.setDefaultSize(20);
        query.setMaxSize(100);
        properties.setQuery(query);
        return new QueryPreviewPlanValidator(properties);
    }

    private QueryAgentPlan queryPlan(List<String> selectFields, Integer size) {
        AgentFilter filter = new AgentFilter();
        filter.setField("name");
        filter.setOperator(AgentOperator.EQ);
        filter.setValue("Alice");

        AgentQuerySpec query = new AgentQuerySpec();
        query.setFilters(List.of(filter));
        query.setSelectFields(selectFields);
        query.setPage(1);
        query.setSize(size);

        QueryAgentPlan plan = new QueryAgentPlan();
        plan.setQuery(query);
        return plan;
    }

    private ExecutionValidationContext context() {
        return context("query.preview");
    }

    private ExecutionValidationContext context(String capabilityId) {
        return context(capabilityId, 5);
    }

    private ExecutionValidationContext contextWithMaxRows(int maxResultRows) {
        return context("query.preview", maxResultRows);
    }

    private ExecutionValidationContext contextWithSortFields(Set<String> sortFields) {
        return new ExecutionValidationContext(
                "query.preview",
                AgentPlanKind.QUERY,
                AgentDomainMode.REQUIRED,
                executionScope(5),
                projection(sortFields),
                null,
                List.of(),
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }

    private ExecutionValidationContext context(String capabilityId, int maxResultRows) {
        return new ExecutionValidationContext(
                capabilityId,
                AgentPlanKind.QUERY,
                AgentDomainMode.REQUIRED,
                executionScope(maxResultRows),
                projection(Set.of()),
                null,
                List.of(),
                NOW.plusSeconds(30),
                new CancellationSource().token());
    }

    private ExecutionScope executionScope() {
        return executionScope(5);
    }

    private ExecutionScope executionScope(int maxResultRows) {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of("query.preview"),
                Set.of("employee"),
                Map.of("employee", Set.of("name", "memberNo")),
                Map.of(),
                com.dylan.agent.kernel.resource.StandardResourceLimits
                        .testEffective(maxResultRows, maxResultRows, 10_000));
    }

    private ExecutionValidationProjection projection(Set<String> sortFields) {
        return new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of(
                        "name", new ExecutionFieldRule(
                                "name",
                                AgentFieldType.STRING,
                                Set.of(AgentOperator.EQ),
                                Set.of(),
                                100,
                                null,
                                null,
                                null),
                        "memberNo", new ExecutionFieldRule(
                                "memberNo",
                                AgentFieldType.STRING,
                                Set.of(AgentOperator.EQ),
                                Set.of(),
                                100,
                                null,
                                null,
                                null)),
                List.of("name"),
                sortFields,
                "catalog-v1");
    }

    private AgentSortSpec sort(String field, String direction) {
        AgentSortSpec sort = new AgentSortSpec();
        sort.setField(field);
        sort.setDirection(direction);
        return sort;
    }
}
