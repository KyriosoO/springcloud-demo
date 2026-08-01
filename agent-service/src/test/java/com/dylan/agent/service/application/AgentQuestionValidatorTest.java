package com.dylan.agent.service.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;

import com.dylan.agent.service.config.AgentIngressProperties;

import org.junit.jupiter.api.Test;

class AgentQuestionValidatorTest {
    private final AgentQuestionValidator validator = new AgentQuestionValidator(properties());

    @Test
    void normalizesExactlyOnceAndCountsUnicodeCodePoints() {
        String supplementary = "\uD83D\uDE00";
        String maximum = supplementary.repeat(4096);

        assertThat(validator.normalize("  税务政策  ")).isEqualTo("税务政策");
        assertThat(validator.normalize(maximum)).isEqualTo(maximum);
        assertThatThrownBy(() -> validator.normalize(maximum + supplementary))
                .isInstanceOf(AgentPublicException.class);
    }

    @Test
    void rejectsNullAndWhitespace() {
        assertThatThrownBy(() -> validator.normalize(null)).isInstanceOf(AgentPublicException.class);
        assertThatThrownBy(() -> validator.normalize("\u3000 ")).isInstanceOf(AgentPublicException.class);
    }

    private AgentIngressProperties properties() {
        return new AgentIngressProperties(4096, 32768, 16384, 8, Duration.ofSeconds(60), Duration.ofMillis(500));
    }
}
