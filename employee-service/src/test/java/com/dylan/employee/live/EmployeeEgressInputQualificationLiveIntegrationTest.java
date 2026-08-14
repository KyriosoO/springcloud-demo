package com.dylan.employee.live;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mockingDetails;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import com.dylan.employee.event.WorkflowInboxProcessor;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.service.EmployeeService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY", matches = "1")
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
class EmployeeEgressInputQualificationLiveIntegrationTest {
    private static final String QUALIFIED_IDENTIFIER_SQL = """
            SELECT ID_CARD_NO
            FROM employee
            WHERE POSITION IS NOT NULL
              AND TRIM(POSITION) <> ''
              AND WORK_BASE_SI IS NOT NULL
              AND TRIM(WORK_BASE_SI) <> ''
            ORDER BY ID_CARD_NO
            LIMIT 1
            """;

    @LocalServerPort
    private int port;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;
    @MockitoSpyBean
    private EmployeeService employeeService;
    @MockitoSpyBean
    private EmployeeMapper employeeMapper;
    @MockitoBean
    private WorkflowInboxProcessor workflowInboxProcessor;

    @Test
    void qualifiesSingleEmployeeWithoutPersistingSensitiveValues() throws Exception {
        assertThat(System.getenv("LLM_API_KEY")).as("model key must not reach qualification").isNull();
        String maintainerIdentifier = System.getenv("EMPLOYEE_EGRESS_QUALIFY_TEST_IDENTIFIER");
        String selectionMode;
        int databaseSelectionRows;
        String identifier;
        if (maintainerIdentifier != null && !maintainerIdentifier.isBlank()) {
            identifier = maintainerIdentifier.trim();
            selectionMode = "maintainer_confirmed";
            databaseSelectionRows = 0;
        } else {
            List<String> candidates = jdbcTemplate.query(
                    QUALIFIED_IDENTIFIER_SQL,
                    (resultSet, rowNumber) -> resultSet.getString(1));
            assertThat(candidates).as("one qualified Employee input must exist").hasSize(1);
            identifier = candidates.getFirst();
            selectionMode = "read_only_database";
            databaseSelectionRows = 1;
        }

        Path repository = Path.of(required("EMPLOYEE_EGRESS_QUALIFY_REPOSITORY_ROOT"));
        Path probeOutput = Path.of(required("EMPLOYEE_EGRESS_QUALIFY_PROBE_OUTPUT"));
        Path pythonLog = Path.of(required("EMPLOYEE_EGRESS_QUALIFY_PYTHON_LOG"));
        Path pythonJunit = Path.of(required("EMPLOYEE_EGRESS_QUALIFY_PYTHON_JUNIT"));
        String adminJwt = required("EMPLOYEE_EGRESS_QUALIFY_ADMIN_JWT");
        ProcessBuilder processBuilder = new ProcessBuilder(
                required("EMPLOYEE_EGRESS_QUALIFY_PYTHON_EXECUTABLE"),
                "-m", "pytest",
                "tests/integration/adapters/employee/test_real_employee_egress_input_qualification.py",
                "-q", "--tb=no", "--junitxml=" + pythonJunit);
        processBuilder.directory(repository.resolve("agent-runtime").toFile());
        processBuilder.redirectErrorStream(true);
        processBuilder.redirectOutput(pythonLog.toFile());
        Map<String, String> environment = processBuilder.environment();
        environment.remove("LLM_API_KEY");
        environment.put("PYTHONPATH", "src;.");
        environment.put("RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY", "1");
        environment.put("EMPLOYEE_EGRESS_QUALIFY_IDENTIFIER", identifier);
        environment.put("EMPLOYEE_EGRESS_QUALIFY_ADMIN_JWT", adminJwt);
        environment.put("EMPLOYEE_EGRESS_QUALIFY_BASE_URL", "http://127.0.0.1:" + port);
        environment.put("EMPLOYEE_EGRESS_QUALIFY_SELECTION_MODE", selectionMode);
        environment.put("EMPLOYEE_EGRESS_QUALIFY_DATABASE_ROWS", Integer.toString(databaseSelectionRows));

        Process process = processBuilder.start();
        boolean finished = process.waitFor(Duration.ofSeconds(60).toMillis(), TimeUnit.MILLISECONDS);
        if (!finished) {
            process.destroyForcibly();
        }
        assertThat(finished).as("qualification Python probe completion").isTrue();
        assertThat(process.exitValue()).as("qualification Python probe exit code").isZero();
        String pythonOutput = Files.readString(pythonLog, StandardCharsets.UTF_8);
        if (pythonOutput.contains(identifier) || pythonOutput.contains(adminJwt)) {
            throw new IllegalStateException("employee.egress_input_qualify_log_leak");
        }

        JsonNode probe = objectMapper.readTree(probeOutput.toFile());
        assertThat(probe.path("status").asText()).isEqualTo("qualified");
        assertThat(probe.path("fieldPresence").path("position").asBoolean()).isTrue();
        assertThat(probe.path("fieldPresence").path("workBaseSi").asBoolean()).isTrue();
        assertThat(probe.path("egressReason").asText()).isEqualTo("qualified");
        assertThat(probe.path("requestCounts").path("databaseSelectionRows").asInt())
                .isEqualTo(databaseSelectionRows);
        assertThat(probe.path("requestCounts").path("employeeDetail").asInt()).isEqualTo(1);
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
        assertThat(serviceDetailCalls).isEqualTo(1);
        assertThat(mapperDetailCalls).isEqualTo(1);
        assertThat(otherServiceCalls).isZero();
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.egress_input_qualify_env_missing:" + name);
        }
        return value;
    }
}
