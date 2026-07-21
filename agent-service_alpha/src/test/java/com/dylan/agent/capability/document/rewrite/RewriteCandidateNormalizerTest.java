package com.dylan.agent.capability.document.rewrite;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class RewriteCandidateNormalizerTest {

    private final RewriteCandidateNormalizer normalizer = new RewriteCandidateNormalizer();

    @Test
    void rejectsDslAndFilterCandidates() {
        QueryVariants variants = normalizer.normalize(
                "增值税优惠政策",
                List.of("增值税"),
                List.of(
                        new DocumentRewriteCandidate("小规模纳税人增值税优惠", "tax", 0.9d),
                        new DocumentRewriteCandidate("{\"filter\":{\"term\":{\"tenantId\":\"t1\"}}}", "dsl", 0.8d),
                        new DocumentRewriteCandidate("使用 indexAlias agent-doc-tax-policy-read 查询", "alias", 0.7d),
                        new DocumentRewriteCandidate("增值税优惠政策", "duplicate", 0.6d)),
                3,
                64);

        assertThat(variants.ruleKeywords()).containsExactly("增值税");
        assertThat(variants.rewriteCandidates()).containsExactly("小规模纳税人增值税优惠");
        assertThat(variants.rejectedCount()).isEqualTo(3);
        assertThat(variants.rewriteCandidateDigest()).startsWith("sha256:");
    }

    @Test
    void limitsCandidateCountAndLength() {
        QueryVariants variants = normalizer.normalize(
                "企业所得税优惠",
                List.of(),
                List.of(
                        new DocumentRewriteCandidate("企业所得税优惠政策", null, null),
                        new DocumentRewriteCandidate("超长候选文本需要被拒绝", null, null),
                        new DocumentRewriteCandidate("企业所得税减免", null, null)),
                1,
                10);

        assertThat(variants.rewriteCandidates()).containsExactly("企业所得税优惠政策");
        assertThat(variants.rejectedCount()).isZero();
    }
}
