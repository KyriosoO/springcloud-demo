package com.dylan.mqprocedureserver.live;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.mockingDetails;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.mockito.invocation.Invocation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import com.dylan.mqprocedureserver.config.TransactionSearchJsonConfiguration;
import com.dylan.mqprocedureserver.config.TransactionSearchProperties;
import com.dylan.mqprocedureserver.controller.TransactionController;
import com.dylan.mqprocedureserver.controller.TransactionExceptionHandler;
import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.mqprocedureserver.security.CapabilityAccessGuard;
import com.dylan.mqprocedureserver.security.TransactionSearchSecurityConfiguration;
import com.dylan.mqprocedureserver.service.TransactionOperKafkaProducer;
import com.dylan.mqprocedureserver.service.TransactionOperMQProducer;
import com.dylan.mqprocedureserver.service.TransactionService;
import com.dylan.transaction.api.model.Transaction;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@EnabledIfEnvironmentVariable(named = "RUN_TRANSACTION_LIVE", matches = "1")
@SpringBootTest(
        classes = TransactionRealActionLiveIntegrationTest.LiveApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "spring.main.banner-mode=off",
                "spring.profiles.active=transaction-live-isolated",
                "spring.cloud.config.enabled=false",
                "spring.config.import=",
                "eureka.client.enabled=false",
                "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,org.mybatis.spring.boot.autoconfigure.MybatisAutoConfiguration,org.redisson.spring.starter.RedissonAutoConfigurationV2",
                "transaction.search.max-exact-total=10000",
                "common.security.secrets.source-order[0]=environment",
                "common.security.secrets.allow-config-values=false",
                "common.security.secrets.fail-fast=true",
                "common.security.secrets.jwt.active-key-id=ACTIVE",
                "common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
                "common.security.secrets.jwt.keys.ACTIVE.value="
        })
class TransactionRealActionLiveIntegrationTest {
    private static final Duration GATEWAY_START_TIMEOUT = Duration.ofSeconds(60);
    private static final Duration GATEWAY_STOP_TIMEOUT = Duration.ofSeconds(5);
    private static final Pattern SAFE_FAILURE_CODE = Pattern.compile("transaction\\.live_[a-z0-9_]+");
    private String livePhase = "bootstrap";

    @LocalServerPort
    private int transactionPort;
    @Autowired
    private ObjectMapper objectMapper;
    @MockitoSpyBean
    private TransactionService transactionService;
    @MockitoBean
    private TransactionMapper transactionMapper;
    @MockitoBean
    private TransactionOperKafkaProducer kafkaProducer;
    @MockitoBean
    private TransactionOperMQProducer mqProducer;

    @Test
    void actualAuthTokensAndFormalGatewayRoutePreserveExactAmountAndCallBoundaries() throws Exception {
        try {
            executeControlledVerification();
        } catch (Exception | AssertionError error) {
            throw new IllegalStateException(safeFailureCode(error, livePhase));
        }
    }

    private void executeControlledVerification() throws Exception {
        Path repository = Path.of(required("TRANSACTION_LIVE_REPOSITORY_ROOT"));
        Path probeEvidence = Path.of(required("TRANSACTION_LIVE_PROBE_EVIDENCE_PATH"));
        Path javaMetrics = Path.of(required("TRANSACTION_LIVE_JAVA_METRICS_PATH"));
        Path pythonLog = Path.of(required("TRANSACTION_LIVE_PYTHON_LOG_PATH"));
        Path pythonJunit = Path.of(required("TRANSACTION_LIVE_PYTHON_JUNIT_PATH"));
        when(transactionMapper.countUpTo(any(Transaction.class), anyInt())).thenReturn(0L);

        livePhase = "python_probe";
        runPythonProbe(repository, pythonLog, pythonJunit);
        livePhase = "probe_contract";
        JsonNode probe = objectMapper.readTree(probeEvidence.toFile());
        assertThat(probe.path("requestCounts").path("transaction").asInt()).isEqualTo(7);
        assertThat(probe.path("requestCounts").path("adapter").asInt()).isEqualTo(6);
        assertThat(probe.path("requestCounts").path("otherTransactionEndpoints").asInt()).isZero();
        assertThat(probe.path("requestCounts").path("model").asInt()).isZero();
        assertThat(probe.path("precisionMatrix").path("jsonNumberOnly").asBoolean()).isTrue();

        livePhase = "direct_contract";
        List<Transaction> directConditions = countConditions();
        assertThat(directConditions).as("transaction.live_direct_mapper_count_invalid").hasSize(3);
        assertExactAmount(directConditions.get(0), "0.01", null, null);
        assertExactAmount(directConditions.get(1), null, "-9999999999999999.99", null);
        assertExactAmount(directConditions.get(2), null, null, "9999999999999999.99");
        assertThat(invocationCount(transactionService, "search")).isEqualTo(3);
        assertThat(invocationCount(transactionMapper, "query")).isZero();
        assertThat(otherServiceCalls()).isZero();

        livePhase = "gateway_start";
        int gatewayPort = requiredPort("TRANSACTION_LIVE_GATEWAY_PORT");
        Process gateway = startGateway(
                Path.of(required("TRANSACTION_LIVE_GATEWAY_JAR")),
                Path.of(required("TRANSACTION_LIVE_GATEWAY_OUT_PATH")),
                Path.of(required("TRANSACTION_LIVE_GATEWAY_ERR_PATH")),
                gatewayPort);
        int responseStatus;
        try {
            waitForListener(gateway, gatewayPort);
            livePhase = "gateway_request";
            responseStatus = invokeGateway(gatewayPort);
        } finally {
            stopGateway(gateway);
        }
        if (responseStatus != 200) {
            throw new IllegalStateException(statusFailure(responseStatus));
        }

        livePhase = "gateway_contract";
        List<Transaction> allConditions = countConditions();
        assertThat(allConditions).as("transaction.live_total_mapper_count_invalid").hasSize(4);
        Transaction gatewayCondition = allConditions.get(3);
        assertThat(gatewayCondition.getTransId()).isEqualTo(required("TRANSACTION_LIVE_GATEWAY_SENTINEL"));
        assertExactAmount(gatewayCondition, "0.01", null, null);
        long serviceSearchCalls = invocationCount(transactionService, "search");
        long mapperCountCalls = invocationCount(transactionMapper, "countUpTo");
        long mapperQueryCalls = invocationCount(transactionMapper, "query");
        long otherServiceCalls = otherServiceCalls();
        assertThat(serviceSearchCalls).isEqualTo(4);
        assertThat(mapperCountCalls).isEqualTo(4);
        assertThat(mapperQueryCalls).isZero();
        assertThat(otherServiceCalls).isZero();

        livePhase = "metrics_write";
        Files.writeString(javaMetrics, objectMapper.writeValueAsString(Map.ofEntries(
                Map.entry("schemaVersion", 1),
                Map.entry("gateway", 1),
                Map.entry("gatewayResponseStatus", responseStatus),
                Map.entry("serviceSearch", serviceSearchCalls),
                Map.entry("mapperCountUpTo", mapperCountCalls),
                Map.entry("mapperQuery", mapperQueryCalls),
                Map.entry("otherServiceMethods", otherServiceCalls),
                Map.entry("amountExact", true),
                Map.entry("amountGtExact", true),
                Map.entry("amountLtExact", true),
                Map.entry("gatewayAmountExact", true),
                Map.entry("mapperValuesUnmodified", true))), StandardCharsets.UTF_8);
    }

    private void runPythonProbe(Path repository, Path pythonLog, Path pythonJunit) throws Exception {
        ProcessBuilder builder = new ProcessBuilder(
                required("TRANSACTION_LIVE_PYTHON_EXECUTABLE"),
                "-m", "pytest",
                "tests/integration/adapters/transaction/test_real_transaction_live.py",
                "-q", "--tb=no", "--junitxml=" + pythonJunit);
        builder.directory(repository.resolve("agent-runtime").toFile());
        builder.redirectErrorStream(true);
        builder.redirectOutput(pythonLog.toFile());
        Map<String, String> environment = builder.environment();
        environment.put("PYTHONPATH", "src");
        environment.put("TRANSACTION_LIVE_BASE_URL", "http://127.0.0.1:" + transactionPort);
        Process process = builder.start();
        boolean finished = process.waitFor(Duration.ofSeconds(60).toMillis(), TimeUnit.MILLISECONDS);
        if (!finished) {
            process.destroyForcibly();
        }
        assertThat(finished).as("transaction.live_python_probe_timeout").isTrue();
        assertThat(process.exitValue()).as("transaction.live_python_probe_failed").isZero();
    }

    private Process startGateway(Path jar, Path stdout, Path stderr, int gatewayPort) throws Exception {
        assertThat(jar).as("transaction.live_gateway_jar_missing").isRegularFile();
        ProcessBuilder builder = new ProcessBuilder(
                "java", "-jar", jar.toString(),
                "--server.port=" + gatewayPort,
                "--spring.main.banner-mode=off",
                "--spring.cloud.config.enabled=false",
                "--spring.config.import=",
                "--eureka.client.enabled=false",
                "--spring.cloud.gateway.server.webflux.discovery.locator.enabled=false",
                "--spring.cloud.gateway.discovery.locator.enabled=false",
                "--spring.cloud.discovery.client.simple.instances.mq-procedure-service[0].uri=http://127.0.0.1:" + transactionPort,
                "--management.endpoints.enabled-by-default=false",
                "--common.security.secrets.source-order[0]=environment",
                "--common.security.secrets.allow-config-values=false",
                "--common.security.secrets.fail-fast=true",
                "--common.security.secrets.jwt.active-key-id=ACTIVE",
                "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
                "--common.security.secrets.jwt.keys.ACTIVE.value=");
        builder.redirectOutput(stdout.toFile());
        builder.redirectError(stderr.toFile());
        Map<String, String> environment = builder.environment();
        environment.keySet().removeIf(name -> name.startsWith("TRANSACTION_LIVE_"));
        environment.remove("RUN_TRANSACTION_LIVE");
        return builder.start();
    }

    private int invokeGateway(int gatewayPort) throws Exception {
        String body = "{\"condition\":{\"transId\":\"" + required("TRANSACTION_LIVE_GATEWAY_SENTINEL")
                + "\",\"amount\":0.01},\"page\":1,\"size\":20,\"sorts\":[]}";
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("http://127.0.0.1:" + gatewayPort + "/txn/search"))
                .timeout(Duration.ofSeconds(10))
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + required("TRANSACTION_LIVE_ADMIN_JWT"))
                .header(HttpHeaders.CONTENT_TYPE, "application/json")
                .header("X-Correlation-Id", required("TRANSACTION_LIVE_CORRELATION_ID"))
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        return HttpClient.newBuilder()
                .followRedirects(HttpClient.Redirect.NEVER)
                .connectTimeout(Duration.ofSeconds(5))
                .build()
                .send(request, HttpResponse.BodyHandlers.discarding())
                .statusCode();
    }

    private List<Transaction> countConditions() {
        return mockingDetails(transactionMapper).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getName().equals("countUpTo"))
                .map(invocation -> (Transaction) invocation.getArgument(0))
                .toList();
    }

    private static void assertExactAmount(Transaction condition, String amount, String amountGt, String amountLt) {
        assertDecimal(condition.getAmount(), amount);
        assertDecimal(condition.getAmountGt(), amountGt);
        assertDecimal(condition.getAmountLt(), amountLt);
        assertThat(condition.getTransDate()).isNull();
        assertThat(condition.getTransDateGt()).isNull();
        assertThat(condition.getTransDateLt()).isNull();
    }

    private static void assertDecimal(BigDecimal actual, String expected) {
        if (expected == null) {
            assertThat(actual).isNull();
        } else {
            assertThat(actual).isEqualByComparingTo(new BigDecimal(expected));
            assertThat(actual.scale()).isEqualTo(new BigDecimal(expected).scale());
        }
    }

    private long otherServiceCalls() {
        return mockingDetails(transactionService).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getDeclaringClass().equals(TransactionService.class))
                .filter(invocation -> java.lang.reflect.Modifier.isPublic(invocation.getMethod().getModifiers()))
                .filter(invocation -> !invocation.getMethod().getName().equals("search"))
                .count();
    }

    private static long invocationCount(Object mock, String methodName) {
        return mockingDetails(mock).getInvocations().stream()
                .map(Invocation::getMethod)
                .filter(method -> method.getName().equals(methodName))
                .count();
    }

    private static void waitForListener(Process process, int port) throws Exception {
        long deadline = System.nanoTime() + GATEWAY_START_TIMEOUT.toNanos();
        while (System.nanoTime() < deadline) {
            if (!process.isAlive()) {
                throw new IllegalStateException("transaction.live_gateway_process_exited");
            }
            try (Socket socket = new Socket()) {
                socket.connect(new InetSocketAddress("127.0.0.1", port), 200);
                return;
            } catch (java.io.IOException ignored) {
                Thread.sleep(200);
            }
        }
        throw new IllegalStateException("transaction.live_gateway_readiness_timeout");
    }

    private static void stopGateway(Process process) throws InterruptedException {
        if (!process.isAlive()) {
            return;
        }
        process.destroy();
        if (!process.waitFor(GATEWAY_STOP_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS)) {
            process.destroyForcibly();
            process.waitFor(GATEWAY_STOP_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
        }
    }

    private static int requiredPort(String name) {
        try {
            int port = Integer.parseInt(required(name));
            if (port < 1024 || port > 65535) {
                throw new NumberFormatException();
            }
            return port;
        } catch (NumberFormatException ex) {
            throw new IllegalStateException("transaction.live_port_invalid");
        }
    }

    private static String statusFailure(int status) {
        if (status == 301 || status == 302 || status == 307 || status == 308 || status == 401 || status == 403) {
            return "transaction.live_gateway_auth_failed";
        }
        if (status == 404) {
            return "transaction.live_gateway_route_missing";
        }
        if (status == 500 || status == 502 || status == 503 || status == 504) {
            return "transaction.live_gateway_forwarding_failed";
        }
        return "transaction.live_gateway_status_invalid";
    }

    private static String safeFailureCode(Throwable error, String phase) {
        Throwable current = error;
        for (int depth = 0; current != null && depth < 8; depth++, current = current.getCause()) {
            String message = current.getMessage();
            if (message != null) {
                Matcher matcher = SAFE_FAILURE_CODE.matcher(message);
                if (matcher.find()) {
                    return matcher.group();
                }
            }
        }
        if (phase.matches("bootstrap|python_probe|probe_contract|direct_contract|gateway_start|gateway_request|gateway_contract|metrics_write")) {
            return "transaction.live_" + phase + "_failed";
        }
        if (error instanceof AssertionError) {
            return "transaction.live_assertion_failed";
        }
        if (error instanceof java.io.IOException) {
            return "transaction.live_io_failed";
        }
        return "transaction.live_java_failed";
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("transaction.live_env_missing:" + name);
        }
        return value;
    }

    @SpringBootConfiguration
    @EnableAutoConfiguration
    @EnableConfigurationProperties(TransactionSearchProperties.class)
    @Import({
            TransactionController.class,
            TransactionExceptionHandler.class,
            TransactionService.class,
            CapabilityAccessGuard.class,
            TransactionSearchSecurityConfiguration.class,
            TransactionSearchJsonConfiguration.class
    })
    static class LiveApplication {
    }
}
