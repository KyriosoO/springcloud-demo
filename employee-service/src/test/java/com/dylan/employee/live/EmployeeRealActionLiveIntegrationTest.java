package com.dylan.employee.live;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mockingDetails;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import com.dylan.employee.event.WorkflowInboxProcessor;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.service.EmployeeService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_LIVE", matches = "1")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.cloud.config.enabled=false",
        "spring.config.import=",
        "spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
        "spring.profiles.active=datasource,emp,ai-provider",
        "eureka.client.enabled=false",
        "spring.kafka.listener.auto-startup=false",
        "employee.workflow.inbox-retry-delay-ms=3600000",
        "common.security.secrets.source-order[0]=environment",
        "common.security.secrets.allow-config-values=false",
        "common.security.secrets.fail-fast=true",
        "common.security.secrets.jwt.active-key-id=ACTIVE",
        "common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "common.security.secrets.jwt.keys.ACTIVE.value="
})
class EmployeeRealActionLiveIntegrationTest {
    @LocalServerPort
    private int port;
    @Autowired
    private ObjectMapper objectMapper;
    @MockitoSpyBean
    private EmployeeService employeeService;
    @MockitoSpyBean
    private EmployeeMapper employeeMapper;
    @MockitoBean
    private WorkflowInboxProcessor workflowInboxProcessor;

    @Test
    void actualAuthTokensTraversePythonAdapterAndPreserveDomainCallBoundary() throws Exception {
        String repository = required("EMPLOYEE_LIVE_REPOSITORY_ROOT");
        Path probeEvidence = Path.of(required("EMPLOYEE_LIVE_PROBE_EVIDENCE_PATH"));
        Path javaMetrics = Path.of(required("EMPLOYEE_LIVE_JAVA_METRICS_PATH"));
        Path pythonLog = Path.of(required("EMPLOYEE_LIVE_PYTHON_LOG_PATH"));
        Path pythonJunit = Path.of(required("EMPLOYEE_LIVE_PYTHON_JUNIT_PATH"));
        ProcessBuilder processBuilder = new ProcessBuilder(
                required("EMPLOYEE_LIVE_PYTHON_EXECUTABLE"),
                "-m", "pytest",
                "tests/integration/adapters/employee/test_real_employee_live.py",
                "-q", "--tb=no", "--junitxml=" + pythonJunit);
        processBuilder.directory(Path.of(repository, "agent-runtime").toFile());
        processBuilder.redirectErrorStream(true);
        processBuilder.redirectOutput(pythonLog.toFile());
        Map<String, String> environment = processBuilder.environment();
        environment.put("PYTHONPATH", "src");
        environment.put("EMPLOYEE_LIVE_BASE_URL", "http://127.0.0.1:" + port);

        Process process = processBuilder.start();
        boolean finished = process.waitFor(Duration.ofSeconds(60).toMillis(), TimeUnit.MILLISECONDS);
        if (!finished) {
            process.destroyForcibly();
        }
        assertThat(finished).as("employee live Python probe completion").isTrue();
        assertThat(process.exitValue()).as("employee live Python probe exit code").isZero();

        JsonNode probe = objectMapper.readTree(probeEvidence.toFile());
        assertThat(probe.path("requestCounts").path("employee").asInt()).isEqualTo(7);
        assertThat(probe.path("requestCounts").path("adapter").asInt()).isEqualTo(6);
        assertThat(probe.path("requestCounts").path("otherEmployeeEndpoints").asInt()).isZero();
        assertThat(probe.path("requestCounts").path("model").asInt()).isZero();

        long serviceDetailCalls = mockingDetails(employeeService).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getName().equals("detail"))
                .count();
        long otherServiceCalls = mockingDetails(employeeService).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getDeclaringClass().equals(EmployeeService.class))
                .filter(invocation -> !invocation.getMethod().getName().equals("detail"))
                .count();
        long mapperDetailCalls = mockingDetails(employeeMapper).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getName().equals("selectByIdCardNo"))
                .count();
        assertThat(serviceDetailCalls).as("allowed Employee service detail calls").isEqualTo(3);
        assertThat(mapperDetailCalls).as("allowed Employee mapper detail calls").isEqualTo(3);
        assertThat(otherServiceCalls).as("out-of-scope Employee service calls").isZero();

        Files.writeString(javaMetrics, objectMapper.writeValueAsString(Map.of(
                "schemaVersion", 1,
                "serviceDetail", serviceDetailCalls,
                "mapperSelectByIdCardNo", mapperDetailCalls,
                "otherServiceMethods", otherServiceCalls)), StandardCharsets.UTF_8);
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.live_env_missing:" + name);
        }
        return value;
    }
}
