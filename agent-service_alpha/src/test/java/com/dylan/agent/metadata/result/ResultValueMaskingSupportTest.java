package com.dylan.agent.metadata.result;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.mask.AddressFieldMasker;
import com.dylan.agent.mask.EmailFieldMasker;
import com.dylan.agent.mask.FieldMasker;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.mask.IdCardFieldMasker;
import com.dylan.agent.mask.MobileFieldMasker;
import com.dylan.agent.mask.NoneFieldMasker;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

class ResultValueMaskingSupportTest {

    @Test
    void filtersUnauthorizedFieldsBeforeMasking() {
        ResultValueMaskingSupport support = new ResultValueMaskingSupport(throwingIdCardRegistry());

        Map<String, Object> filtered = support.filterAndMaskRow(
                "employee",
                Map.of("chineseName", "张三", "idCardNo", "110101199001010011"),
                scope(Map.of("employee", Set.of("chineseName")), Map.of("employee.idCardNo", MaskType.ID_CARD)));

        assertThat(filtered)
                .containsExactly(Map.entry("chineseName", "张三"));
    }

    @Test
    void appliesConfiguredMaskForCanonicalField() {
        ResultValueMaskingSupport support = new ResultValueMaskingSupport(maskerRegistry());

        Map<String, Object> filtered = support.filterAndMaskRow(
                "employee",
                Map.of("idCardNo", "110101199001010011"),
                scope(Map.of("employee", Set.of("idCardNo")), Map.of("employee.idCardNo", MaskType.ID_CARD)));

        assertThat(filtered)
                .containsExactly(Map.entry("idCardNo", "110101********0011"));
    }

    @Test
    void keepsOriginalValueWhenMaskMissingOrNone() {
        ResultValueMaskingSupport support = new ResultValueMaskingSupport(maskerRegistry());

        assertThat(support.maskValue("employee", "chineseName", "张三",
                scope(Map.of("employee", Set.of("chineseName")), Map.of())))
                .isEqualTo("张三");
        assertThat(support.maskValue("employee", "chineseName", "张三",
                scope(Map.of("employee", Set.of("chineseName")), Map.of("employee.chineseName", MaskType.NONE))))
                .isEqualTo("张三");
    }

    @Test
    void masksFilterValueListAsStringValues() {
        ResultValueMaskingSupport support = new ResultValueMaskingSupport(maskerRegistry());
        AgentQueryFilterParameter filter = new AgentQueryFilterParameter();
        filter.setField("phoneNo");
        filter.setValues(List.of("13812345678", "13912345678"));

        AgentQueryFilterParameter filtered = support.filterAndMaskFilter(
                "employee",
                filter,
                scope(Map.of("employee", Set.of("phoneNo")), Map.of("employee.phoneNo", MaskType.MOBILE)));

        assertThat(filtered.getValues())
                .containsExactly("138****5678", "139****5678");
    }

    private ExecutionScope scope(
            Map<String, Set<String>> allowedFields,
            Map<String, MaskType> fieldMasks) {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                allowedFields,
                fieldMasks,
                com.dylan.agent.kernel.resource.StandardResourceLimits
                        .testEffective(100, 100, 10_000));
    }

    private FieldMaskerRegistry maskerRegistry() {
        return new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker()));
    }

    private FieldMaskerRegistry throwingIdCardRegistry() {
        return new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new FieldMasker() {
                    @Override
                    public MaskType type() {
                        return MaskType.ID_CARD;
                    }

                    @Override
                    public Object mask(Object value) {
                        throw new IllegalStateException("id card mask should not be called");
                    }
                },
                new MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker()));
    }
}
