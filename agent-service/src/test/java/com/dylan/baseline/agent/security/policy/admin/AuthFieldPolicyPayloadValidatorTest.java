package com.dylan.baseline.agent.security.policy.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class AuthFieldPolicyPayloadValidatorTest {

    private final AuthFieldPolicyPayloadValidator validator =
            new AuthFieldPolicyPayloadValidator(new ObjectMapper());

    @Test
    void canonicalizesObjectAndSetOrderToTheSameDigest() {
        String first = payload("[\"name\",\"email\"]");
        String second = """
                {"fieldPolicies":{"viewer":{"allowedFunctions":{},"allowedOperators":{},
                "displayableFields":{"employee":["email","name"]},
                "filterableFields":{"employee":["email","name"]}}}}
                """;

        assertThat(validator.validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, first).digest())
                .isEqualTo(validator.validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, second).digest());
    }

    @Test
    void rejectsAdditionalFieldsDuplicatesAndNonAsciiIdentifiers() {
        assertInvalid(payload("[\"name\",\"name\"]"));
        assertInvalid(payload("[\"姓名\"]"));
        assertInvalid(payload("[\"name\"]").replace(
                "\"allowedFunctions\":{}", "\"allowedFunctions\":{},\"roles\":[\"admin\"]"));
        assertInvalid("x".repeat(1_048_577));
    }

    private void assertInvalid(String payload) {
        assertThatThrownBy(() -> validator.validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, payload))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_PAYLOAD_INVALID"));
    }

    private static String payload(String fields) {
        return """
                {"fieldPolicies":{"viewer":{"filterableFields":{"employee":%s},
                "displayableFields":{"employee":%s},"allowedOperators":{},"allowedFunctions":{}}}}
                """.formatted(fields, fields);
    }
}
