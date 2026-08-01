package com.dylan.agent.service.web;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.stream.Stream;

import com.dylan.agent.service.contract.AgentQueryResponse;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureResponse;
import com.dylan.agent.service.contract.FailureSource;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.http.HttpStatus;

class AgentQueryControllerTest {

    @ParameterizedTest
    @MethodSource("semanticStatuses")
    void mapsEverySemanticStatusWithoutChangingItsMeaning(CapabilityStatus status, HttpStatus expected) {
        boolean successLike = status == CapabilityStatus.SUCCESS || status == CapabilityStatus.NO_RESULT;
        AgentQueryResponse response = new AgentQueryResponse(
                "req", "corr", status, null, "safe", null,
                successLike ? null : new FailureResponse("core.test_failure", FailureSource.CORE));

        assertThat(AgentQueryController.httpStatus(response)).isEqualTo(expected);
    }

    @Test
    void mapsOnlySpringCapacityFailureTo429() {
        AgentQueryResponse springCapacity = failure("core.ingress_capacity_exceeded");
        AgentQueryResponse runtimeCapacity = failure("core.runtime_capacity_exceeded");

        assertThat(AgentQueryController.httpStatus(springCapacity)).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
        assertThat(AgentQueryController.httpStatus(runtimeCapacity)).isEqualTo(HttpStatus.BAD_GATEWAY);
    }

    private AgentQueryResponse failure(String code) {
        return new AgentQueryResponse(
                "req", "corr", CapabilityStatus.DOWNSTREAM_FAILURE, null,
                "下游查询暂时不可用。", null, new FailureResponse(code, FailureSource.CORE));
    }

    private static Stream<Arguments> semanticStatuses() {
        return Stream.of(
                Arguments.of(CapabilityStatus.SUCCESS, HttpStatus.OK),
                Arguments.of(CapabilityStatus.NO_RESULT, HttpStatus.OK),
                Arguments.of(CapabilityStatus.UNSUPPORTED, HttpStatus.UNPROCESSABLE_ENTITY),
                Arguments.of(CapabilityStatus.INVALID_ARGUMENT, HttpStatus.BAD_REQUEST),
                Arguments.of(CapabilityStatus.UNAUTHENTICATED, HttpStatus.UNAUTHORIZED),
                Arguments.of(CapabilityStatus.FORBIDDEN, HttpStatus.FORBIDDEN),
                Arguments.of(CapabilityStatus.MODEL_EGRESS_DENIED, HttpStatus.FORBIDDEN),
                Arguments.of(CapabilityStatus.TIMEOUT, HttpStatus.GATEWAY_TIMEOUT),
                Arguments.of(CapabilityStatus.DOWNSTREAM_FAILURE, HttpStatus.BAD_GATEWAY),
                Arguments.of(CapabilityStatus.INTERNAL_FAILURE, HttpStatus.INTERNAL_SERVER_ERROR));
    }
}
