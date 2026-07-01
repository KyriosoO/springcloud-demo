package com.dylan.agent.config;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.QueryableAdapterRegistry;
import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.capability.AgentCapabilityHandlerRegistry;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedCapabilityPlan;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.model.MaskType;

@DisplayName("AgentPropertiesValidator")
class AgentPropertiesValidatorTest {

    private AgentProperties properties;
    private QueryableAdapterRegistry adapterRegistry;
    private AgentCapabilityHandlerRegistry handlerRegistry;
    private AggregatableAdapterRegistry aggregateAdapterRegistry;

    @BeforeEach
    void setUp() {
        properties = validProperties();
        adapterRegistry = new QueryableAdapterRegistry(List.of(new TestEmployeeAdapter()));
        aggregateAdapterRegistry = new AggregatableAdapterRegistry(List.of(new TestAggregateAdapter()));
        var queryHandler = new TestCapabilityHandler(AgentIntent.QUERY);
        var clarifyHandler = new TestCapabilityHandler(AgentIntent.CLARIFY);
        var aggregateHandler = new TestCapabilityHandler(AgentIntent.AGGREGATE);
        handlerRegistry = new AgentCapabilityHandlerRegistry(List.of(queryHandler, clarifyHandler, aggregateHandler));
    }

    @Nested
    @DisplayName("启动成功场景")
    class ValidScenarios {

        @Test
        @DisplayName("完整合法配置不抛异常")
        void shouldPassWithValidConfig() {
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
        }
    }

    @Nested
    @DisplayName("字段配置校验")
    class FieldConfigValidation {

        @Test
        @DisplayName("默认展示字段不存在时启动失败")
        void shouldFailWhenDefaultSelectFieldNotConfigured() {
            properties.getDomains().get("employee").setDefaultSelectFields(List.of("chineseName", "nonExistentField"));
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("default select field");
        }

        @Test
        @DisplayName("未知 mask 类型启动失败（在 FieldMaskerRegistry 启动校验）")
        void shouldNotFailForMaskTypeHere() {
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("字段 filter-roles 为空时启动失败")
        void shouldFailWhenFilterRolesEmpty() {
            properties.getDomains().get("employee").getFields().get("chineseName").setFilterRoles(Set.of());
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("chineseName");
        }

        @Test
        @DisplayName("字段 display-roles 为空时启动失败")
        void shouldFailWhenDisplayRolesEmpty() {
            properties.getDomains().get("employee").getFields().get("position").setDisplayRoles(Set.of());
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("position");
        }

        @Test
        @DisplayName("配置字段与 Adapter supportedFields 不一致时启动失败")
        void shouldFailWhenFieldsMismatchAdapter() {
            var fields = new HashMap<>(properties.getDomains().get("employee").getFields());
            fields.remove("email");
            properties.getDomains().get("employee").setFields(fields);
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("Adapter");
        }

        @Test
        @DisplayName("DECIMAL 未配置 precision/scale 时启动失败")
        void shouldFailWhenDecimalPrecisionIsMissing() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.IN));
            field.setType(AgentFieldType.DECIMAL);

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("decimal-precision")
                    .hasMessageContaining("decimal-scale");
        }

        @Test
        @DisplayName("DECIMAL precision/scale 合法时启动成功")
        void shouldPassWithValidDecimalPrecisionAndScale() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.IN));
            field.setType(AgentFieldType.DECIMAL);
            field.setDecimalPrecision(50);
            field.setDecimalScale(2);

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("DECIMAL scale 大于 precision 时启动失败")
        void shouldFailWhenDecimalScaleExceedsPrecision() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.IN));
            field.setType(AgentFieldType.DECIMAL);
            field.setDecimalPrecision(2);
            field.setDecimalScale(3);

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("decimal-scale");
        }

        @Test
        @DisplayName("非 DECIMAL 配置 precision/scale 时启动失败")
        void shouldFailWhenStringHasDecimalConfiguration() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setDecimalPrecision(50);
            field.setDecimalScale(2);

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("非 DECIMAL");
        }

        @Test
        @DisplayName("STRING 字段配置 GT 时启动失败")
        void shouldFailStringWithGt() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.GT));

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("不兼容");
        }

        @Test
        @DisplayName("DECIMAL 字段配置 CONTAINS 时启动失败")
        void shouldFailDecimalWithContains() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setType(AgentFieldType.DECIMAL);
            field.setDecimalPrecision(50);
            field.setDecimalScale(2);
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.CONTAINS));

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("不兼容");
        }

        @Test
        @DisplayName("INSTANT 字段配置 STARTS_WITH 时启动失败")
        void shouldFailInstantWithStartsWith() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setType(AgentFieldType.INSTANT);
            field.setFormatHint("ISO-8601 datetime with timezone");
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.STARTS_WITH));

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("不兼容");
        }

        @Test
        @DisplayName("DECIMAL 配置 EQ/IN/GT/LT 时启动成功")
        void shouldPassDecimalWithEqInGtLt() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setType(AgentFieldType.DECIMAL);
            field.setDecimalPrecision(50);
            field.setDecimalScale(2);
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.IN, AgentOperator.GT, AgentOperator.LT));

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
        }

        @Test
        @DisplayName("INSTANT 配置 EQ/IN/GT/LT 时启动成功")
        void shouldPassInstantWithEqInGtLt() {
            var field = properties.getDomains().get("employee")
                    .getFields().get("chineseName");
            field.setType(AgentFieldType.INSTANT);
            field.setFormatHint("ISO-8601 datetime with timezone");
            field.setOperators(Set.of(AgentOperator.EQ, AgentOperator.IN, AgentOperator.GT, AgentOperator.LT));

            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);

            assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
        }
    }

    @Nested
    @DisplayName("查询配置校验")
    class QueryValidation {

        @Test
        @DisplayName("defaultSize > maxSize 时启动失败")
        void shouldFailWhenDefaultAboveMax() {
            properties.getQuery().setDefaultSize(200);
            properties.getQuery().setMaxSize(100);
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("default-size");
        }

        @Test
        @DisplayName("maxSize > maxResultWindow 时启动失败")
        void shouldFailWhenMaxSizeExceedsWindow() {
            properties.getQuery().setMaxSize(200);
            properties.getQuery().setMaxResultWindow(100);
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class);
        }
    }

    @Nested
    @DisplayName("Runtime 配置校验")
    class RuntimeValidation {

        @Test
        @DisplayName("shared-key 不足 16 字符时启动失败")
        void shouldFailWhenSharedKeyTooShort() {
            properties.getRuntime().setSharedKey("short");
            var validator = new AgentPropertiesValidator(properties, adapterRegistry, handlerRegistry, aggregateAdapterRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("shared-key");
        }
    }

    private AgentProperties validProperties() {
        AgentProperties p = new AgentProperties();
        p.setIntentRoles(Map.of(
                AgentIntent.QUERY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.CLARIFY, Set.of("agent:viewer", "agent:admin"),
                AgentIntent.AGGREGATE, Set.of("agent:viewer", "agent:admin")));

        AgentProperties.RuntimeProperties rt = new AgentProperties.RuntimeProperties();
        rt.setBaseUrl("http://localhost:9230");
        rt.setSharedKey("test-key-at-least-16-characters");
        rt.setConnectTimeout(java.time.Duration.ofSeconds(2));
        rt.setReadTimeout(java.time.Duration.ofSeconds(15));
        rt.setMaxResponseBytes(65536);
        p.setRuntime(rt);

        AgentProperties.ConversationProperties conv = new AgentProperties.ConversationProperties();
        conv.setRecentTurnLimit(6);
        conv.setRetentionDays(7);
        conv.setCleanupDelay(java.time.Duration.ofHours(1));
        p.setConversation(conv);

        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setDefaultSize(20);
        q.setMaxSize(100);
        q.setMaxResultWindow(10000);
        q.setMaxFilters(5);
        q.setMaxInValues(20);
        q.setMaxFilterValueLength(256);
        q.setMaxDownstreamResponseBytes(2097152);
        p.setQuery(q);

        var agg = new AgentProperties.AggregateProperties();
        agg.setMaxMetrics(5);
        agg.setMaxGroupFields(2);
        agg.setDefaultMaxRows(20);
        agg.setMaxMaxRows(100);
        p.setAggregate(agg);

        Map<String, AgentProperties.FieldProperties> fields = new HashMap<>();
        fields.put("chineseName", makeField(List.of("姓名"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin"), MaskType.NONE));
        fields.put("memberNo", makeField(List.of("工号"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin"), MaskType.NONE));
        fields.put("position", makeField(List.of("岗位"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:viewer", "agent:admin"), Set.of("agent:viewer", "agent:admin"), MaskType.NONE));
        fields.put("contactAddress", makeField(List.of("地址"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:admin"), Set.of("agent:admin"), MaskType.ADDRESS));
        fields.put("idCardNo", makeField(List.of("身份证号"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:admin"), Set.of("agent:admin"), MaskType.ID_CARD));
        fields.put("phoneNo", makeField(List.of("手机号"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:admin"), Set.of("agent:admin"), MaskType.MOBILE));
        fields.put("email", makeField(List.of("邮箱"), Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN),
                Set.of("agent:admin"), Set.of("agent:admin"), MaskType.EMAIL));

        AgentProperties.DomainProperties emp = new AgentProperties.DomainProperties();
        emp.setAliases(List.of("员工", "employee"));
        emp.setAccessRoles(Set.of("agent:viewer", "agent:admin"));
        emp.setDefaultSelectFields(List.of("chineseName", "memberNo", "position"));
        emp.setFields(fields);
        p.setDomains(Map.of("employee", emp));

        return p;
    }

    private AgentProperties.FieldProperties makeField(List<String> aliases, Set<AgentOperator> ops,
                                                      Set<String> filterRoles, Set<String> displayRoles, MaskType mask) {
        AgentProperties.FieldProperties fp = new AgentProperties.FieldProperties();
        fp.setAliases(aliases);
        fp.setType(AgentFieldType.STRING);
        fp.setOperators(ops);
        fp.setFilterRoles(filterRoles);
        fp.setDisplayRoles(displayRoles);
        fp.setMask(mask);
        return fp;
    }

    static class TestEmployeeAdapter implements QueryableAdapter {
        @Override public String domain() { return "employee"; }
        @Override public java.util.Set<String> supportedFields() {
            return java.util.Set.of("chineseName", "memberNo", "position", "contactAddress", "idCardNo", "phoneNo", "email");
        }
        @Override public AdapterQueryResult query(ValidatedQuery query) {
            return new AdapterQueryResult(List.of(), 0, 1, 20);
        }
    }

    static class TestAggregateAdapter implements AggregatableAdapter {
        @Override public String domain() { return "employee"; }
        @Override public java.util.Set<String> supportedAggregateFields() { return java.util.Set.of("amount"); }
        @Override public Set<AggregateFunction> supportedFunctions(String field) { return Set.of(AggregateFunction.COUNT); }
        @Override public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) { return new AdapterAggregateResult(List.of(), false); }
    }

    private static final class TestCapabilityHandler implements AgentCapabilityHandler<ValidatedCapabilityPlan> {
        private final AgentIntent intent;

        TestCapabilityHandler(AgentIntent intent) {
            this.intent = intent;
        }

        @Override
        public AgentIntent intent() { return intent; }

        @Override
        public AgentCapabilityRiskLevel riskLevel() { return AgentCapabilityRiskLevel.READ_ONLY; }

        @Override
        public ValidatedCapabilityPlan validate(CapabilityValidationContext context) { return null; }

        @Override
        public CapabilityExecutionResult execute(CapabilityExecutionContext context, ValidatedCapabilityPlan plan) { return null; }
    }
}
