package com.dylan.agent.planning.filter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("FilterNormalizer")
class FilterNormalizerTest {

    private FilterNormalizer normalizer;
    private DomainView dp;

    @BeforeEach
    void setUp() {
        AgentProperties props = DomainMetadataTestSupport.agentProperties();
        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setMaxFilterValueLength(256);
        q.setMaxInValues(20);
        props.setQuery(q);

        normalizer = new FilterNormalizer(props);
        dp = DomainMetadataTestSupport.catalogView().requireDomain("employee", AdapterRole.QUERYABLE);
    }

    @Nested
    @DisplayName("成功场景")
    class Success {

        @Test
        @DisplayName("STRING EQ 值被 trim")
        void shouldTrimStringEq() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("  张三  ");

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getField()).isEqualTo("chineseName");
            assertThat(result.getOperator()).isEqualTo(AgentOperator.EQ);
            assertThat(result.getValue()).isEqualTo("张三");
            assertThat(result.getValues()).isEmpty();
        }

        @Test
        @DisplayName("CONTAINS 通过")
        void shouldPassContains() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.CONTAINS);
            filter.setValue("北京");

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getOperator()).isEqualTo(AgentOperator.CONTAINS);
            assertThat(result.getValue()).isEqualTo("北京");
        }

        @Test
        @DisplayName("CONTAINS_ANY 去重保序")
        void shouldDedupContainsAny() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.CONTAINS_ANY);
            filter.setValues(List.of("北京", "上海", "北京", "广州"));

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getValues()).containsExactly("北京", "上海", "广州");
        }

        @Test
        @DisplayName("STARTS_WITH_ANY 去重保序")
        void shouldDedupStartsWithAny() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.STARTS_WITH_ANY);
            filter.setValues(List.of("张", "李", "张", "王"));

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getValues()).containsExactly("张", "李", "王");
        }

        @Test
        @DisplayName("IN 去重保序")
        void shouldDedupIn() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.IN);
            filter.setValues(List.of("张三", "李四", "张三", "王五"));

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getOperator()).isEqualTo(AgentOperator.IN);
            assertThat(result.getValues()).containsExactly("张三", "李四", "王五");
            assertThat(result.getValue()).isNull();
        }

        @Test
        @DisplayName("DECIMAL 去前导零和尾随零")
        void shouldNormalizeDecimalLeadingAndTrailingZeros() {
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("000100.50");

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getValue()).isEqualTo("100.5");
        }

        @Test
        @DisplayName("DECIMAL 零统一输出 '0'")
        void shouldNormalizeZeroDecimal() {
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("-0.00");

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getValue()).isEqualTo("0");
        }

        @Test
        @DisplayName("INSTANT 转 UTC")
        void shouldNormalizeInstantToUtc() {
            AgentFilter filter = new AgentFilter();
            filter.setField("transDate");
            filter.setOperator(AgentOperator.GT);
            filter.setValue("2026-06-22T10:30:00+08:00");

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getValue()).isEqualTo("2026-06-22T02:30:00Z");
        }

        @Test
        @DisplayName("多值 DECIMAL 逐项规范化")
        void shouldNormalizeMultiDecimalValues() {
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.IN);
            filter.setValues(List.of("100.50", "0200.00"));

            ValidatedFilter result = normalizer.normalize(filter, dp);
            assertThat(result.getValues()).containsExactly("100.5", "200");
        }

        @Test
        @DisplayName("normalizeAll 返回不可修改列表")
        void shouldReturnUnmodifiableList() {
            List<ValidatedFilter> emptyResult = normalizer.normalizeAll(List.of(), dp);
            assertThat(emptyResult).isEmpty();

            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("test");
            List<ValidatedFilter> result = normalizer.normalizeAll(List.of(filter), dp);
            assertThat(result).hasSize(1);
            assertThatThrownBy(() -> result.add(null)).isInstanceOf(UnsupportedOperationException.class);
        }
    }

    @Nested
    @DisplayName("拒绝场景")
    class Rejection {

        @Test
        @DisplayName("null filter 拒绝")
        void shouldRejectNullFilter() {
            assertThatThrownBy(() -> normalizer.normalize(null, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("filter");
        }

        @Test
        @DisplayName("blank field 拒绝")
        void shouldRejectBlankField() {
            AgentFilter filter = new AgentFilter();
            filter.setField("  ");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("test");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("field");
        }

        @Test
        @DisplayName("null operator 拒绝")
        void shouldRejectNullOperator() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setValue("test");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("operator");
        }

        @Test
        @DisplayName("未知 field 拒绝")
        void shouldRejectUnknownField() {
            AgentFilter filter = new AgentFilter();
            filter.setField("nonExistentField");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("test");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("未知");
        }

        @Test
        @DisplayName("operator 不在配置 allowlist 时拒绝")
        void shouldRejectOperatorNotInAllowlist() {
            AgentFilter filter = new AgentFilter();
            filter.setField("transDate");
            filter.setOperator(AgentOperator.STARTS_WITH);
            filter.setValue("2026-06-22T10:30:00+08:00");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("不支持 operator");
        }

        @Test
        @DisplayName("STRING + GT 类型不兼容拒绝")
        void shouldRejectStringWithGt() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.GT);
            filter.setValue("test");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("不支持 operator");
        }

        @Test
        @DisplayName("DECIMAL + CONTAINS 类型不兼容拒绝")
        void shouldRejectDecimalWithContains() {
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.CONTAINS);
            filter.setValue("test");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("不支持 operator");
        }

        @Test
        @DisplayName("INSTANT + STARTS_WITH 类型不兼容拒绝")
        void shouldRejectInstantWithStartsWith() {
            AgentFilter filter = new AgentFilter();
            filter.setField("transDate");
            filter.setOperator(AgentOperator.STARTS_WITH);
            filter.setValue("2026");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("不支持 operator");
        }

        @Test
        @DisplayName("SINGLE 携带 values 拒绝")
        void shouldRejectSingleWithValues() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.EQ);
            filter.setValues(List.of("A"));

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("不允许 values");
        }

        @Test
        @DisplayName("MULTI 携带 value 拒绝")
        void shouldRejectMultiWithValue() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.IN);
            filter.setValue("test");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("不允许 value");
        }

        @Test
        @DisplayName("MULTI values 为空拒绝")
        void shouldRejectMultiWithEmptyValues() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.IN);
            filter.setValues(List.of());

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("非空 values");
        }

        @Test
        @DisplayName("value 超长拒绝")
        void shouldRejectOversizedValue() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("x".repeat(300));

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("长度");
        }

        @Test
        @DisplayName("控制字符拒绝")
        void shouldRejectControlChars() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("test x");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("控制字符");
        }

        @Test
        @DisplayName("CONTAINS wildcard 元字符拒绝")
        void shouldRejectContainsWildcard() {
            AgentFilter filter = new AgentFilter();
            filter.setField("chineseName");
            filter.setOperator(AgentOperator.CONTAINS);
            filter.setValue("test*");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("wildcard");
        }

        @Test
        @DisplayName("DECIMAL 科学计数法拒绝")
        void shouldRejectScientificDecimal() {
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("1E+10");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("DECIMAL");
        }

        @Test
        @DisplayName("DECIMAL precision 超限拒绝")
        void shouldRejectDecimalPrecisionOverflow() {
            // amount field has precision=50, scale=2, so integer part max 48 digits
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("1".repeat(50)); // 50 digits integer > 48

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("DECIMAL");
        }

        @Test
        @DisplayName("DECIMAL scale 超限拒绝")
        void shouldRejectDecimalScaleOverflow() {
            AgentFilter filter = new AgentFilter();
            filter.setField("amount");
            filter.setOperator(AgentOperator.EQ);
            filter.setValue("1.123"); // scale 3 > 2

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("DECIMAL");
        }

        @Test
        @DisplayName("INSTANT 无时区拒绝")
        void shouldRejectInstantWithoutOffset() {
            AgentFilter filter = new AgentFilter();
            filter.setField("transDate");
            filter.setOperator(AgentOperator.GT);
            filter.setValue("2026-06-22T10:30:00");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("INSTANT");
        }

        @Test
        @DisplayName("INSTANT 小数秒拒绝")
        void shouldRejectInstantFractionalSecond() {
            AgentFilter filter = new AgentFilter();
            filter.setField("transDate");
            filter.setOperator(AgentOperator.GT);
            filter.setValue("2026-06-22T10:30:00.001+08:00");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("小数秒");
        }

        @Test
        @DisplayName("INSTANT 秒级 offset 拒绝")
        void shouldRejectInstantSecondPrecisionOffset() {
            AgentFilter filter = new AgentFilter();
            filter.setField("transDate");
            filter.setOperator(AgentOperator.GT);
            filter.setValue("2026-06-22T10:30:00+08:00:01");

            assertThatThrownBy(() -> normalizer.normalize(filter, dp))
                    .isInstanceOf(AgentPlanValidationException.class)
                    .hasMessageContaining("INSTANT");
        }
    }

}
