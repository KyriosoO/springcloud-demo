package com.dylan.baseline.agent.security.migration.control;

import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.ActivationCommand;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.AuthenticatedActor;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.ChangeClass;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.Operation;
import com.dylan.baseline.agent.security.policy.internal.AgentSecurityPolicyRecordMapper;
import com.dylan.baseline.agent.security.policy.internal.MyBatisAgentSecurityPolicyRepository;
import com.dylan.common.security.IntegrityVerificationKeyProvider;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.time.Clock;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.ibatis.session.SqlSessionFactory;
import org.mybatis.spring.SqlSessionFactoryBean;
import org.mybatis.spring.SqlSessionTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;

/** DR-04-045三步受控迁移CLI；只接受空库或本记录产生的精确可恢复状态。 */
public final class Open04001ControlledMigrationCli {

    private Open04001ControlledMigrationCli() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> values = parse(args);
        String password = System.getenv("OPEN04001_DB_PASSWORD");
        if (password == null || password.isBlank()) {
            throw new IllegalArgumentException("OPEN04001_DB_PASSWORD is required");
        }
        ObjectMapper mapper = new ObjectMapper();
        Path root = Path.of(require(values, "root")).toAbsolutePath().normalize();
        Path recordPath = resolveInside(root, require(values, "record"));
        JsonNode record = mapper.readTree(Files.readAllBytes(recordPath));
        byte[] publicKeyDer = Files.readAllBytes(Path.of(require(values, "public-key")));
        PublicKey publicKey = KeyFactory.getInstance("Ed25519").generatePublic(
                new X509EncodedKeySpec(publicKeyDer));
        String expectedKeyId = require(values, "key-id");
        String expectedKeyVersion = require(values, "key-version");
        String approverRefDigest = require(values, "approver-ref-digest");
        IntegrityVerificationKeyProvider keys = keyRef -> {
            if (!expectedKeyId.equals(keyRef.keyId()) || !expectedKeyVersion.equals(keyRef.keyVersion())) {
                throw new IllegalArgumentException("verification key reference does not match controlled trust config");
            }
            return publicKey;
        };
        AuthFieldPolicyPayloadValidator validator = new AuthFieldPolicyPayloadValidator(mapper);
        var approval = new Open04001MigrationApprovalEvidenceAdapter(
                root, recordPath, require(values, "repository-revision"),
                Open04001ExecutionBinding.configurationDigest(
                        expectedKeyId, expectedKeyVersion, approverRefDigest, publicKeyDer),
                Open04001ExecutionBinding.databaseRefDigest(
                        require(values, "jdbc-url"), values.getOrDefault("db-user", "root")),
                approverRefDigest, keys, validator, mapper, Clock.systemUTC());

        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl(require(values, "jdbc-url"));
        dataSource.setUsername(values.getOrDefault("db-user", "root"));
        dataSource.setPassword(password);
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);

        org.apache.ibatis.session.Configuration mybatis = new org.apache.ibatis.session.Configuration();
        mybatis.addMapper(AgentSecurityPolicyRecordMapper.class);
        SqlSessionFactoryBean factoryBean = new SqlSessionFactoryBean();
        factoryBean.setDataSource(dataSource);
        factoryBean.setConfiguration(mybatis);
        factoryBean.afterPropertiesSet();
        SqlSessionFactory factory = factoryBean.getObject();
        if (factory == null) {
            throw new IllegalStateException("SqlSessionFactory is unavailable");
        }
        AgentSecurityPolicyRecordMapper policyMapper =
                new SqlSessionTemplate(factory).getMapper(AgentSecurityPolicyRecordMapper.class);
        var transactionManager = new DataSourceTransactionManager(dataSource);
        var repository = new MyBatisAgentSecurityPolicyRepository(
                policyMapper, new TransactionTemplate(transactionManager));
        var service = new SecurityPolicyAdministrationService(repository, approval, validator, Clock.systemUTC());

        Map<String, PolicyPayload> policies = Map.of(
                record.get("policyDigest").textValue(), new PolicyPayload(
                        record.get("policyVersion").textValue(), record.get("policySchemaVersion").textValue(),
                        Files.readString(resolveInside(root, record.get("policyPayloadRef").textValue()))),
                record.get("rollbackExercisePolicyDigest").textValue(), new PolicyPayload(
                        record.get("rollbackExercisePolicyVersion").textValue(),
                        record.get("rollbackExercisePolicySchemaVersion").textValue(),
                        Files.readString(resolveInside(root, record.get("rollbackExercisePolicyPayloadRef").textValue()))));
        String approvalRef = record.get("recordId").textValue();
        String actorDigest = record.get("operatorRefDigest").textValue();
        String primaryDigest = record.get("policyDigest").textValue();
        String drillDigest = record.get("rollbackExercisePolicyDigest").textValue();
        int startStep = determineStartStep(jdbc, primaryDigest, drillDigest);
        if (startStep == 3) {
            JsonNode rollback = record.get("policyOperations").get(2);
            approval.verify(new ApprovalVerificationRequest(
                    approvalRef, rollback.get("operation").textValue(), rollback.get("fromPolicyDigest").textValue(),
                    rollback.get("toPolicyDigest").textValue(), rollback.get("changeClass").textValue(),
                    rollback.get("expectedStateVersion").longValue(), actorDigest));
        }
        List<Map<String, Object>> results = new ArrayList<>();
        for (int index = startStep; index < record.get("policyOperations").size(); index++) {
            JsonNode operation = record.get("policyOperations").get(index);
            String targetDigest = operation.get("toPolicyDigest").textValue();
            PolicyPayload target = policies.get(targetDigest);
            Operation operationType = Operation.valueOf(operation.get("operation").textValue());
            boolean create = operationType == Operation.CREATE_AND_ACTIVATE;
            var result = service.activate(new ActivationCommand(
                    operationType, target.version(), create ? target.schema() : null,
                    create ? target.payload() : null, targetDigest,
                    ChangeClass.valueOf(operation.get("changeClass").textValue()),
                    operation.get("expectedStateVersion").longValue(), approvalRef,
                    new AuthenticatedActor("CONTROLLED_MIGRATION", actorDigest, true),
                    "open-04-001-step-" + (index + 1)));
            results.add(Map.of(
                    "step", index + 1, "policyVersion", result.policyVersion(),
                    "policyDigest", result.policyDigest(), "policyEpoch", result.policyEpoch(),
                    "stateVersion", result.stateVersion()));
        }
        Map<String, Object> finalState = jdbc.queryForMap("""
                SELECT policy_version AS policyVersion, policy_digest AS policyDigest,
                       policy_epoch AS policyEpoch, state_version AS stateVersion
                  FROM agent_security_policy_active WHERE scope='GLOBAL'
                """);
        if (!primaryDigest.equals(finalState.get("policyDigest"))
                || ((Number) finalState.get("policyEpoch")).longValue() != 3
                || ((Number) finalState.get("stateVersion")).longValue() != 3
                || count(jdbc, "agent_security_policy_version") != 2
                || count(jdbc, "agent_security_policy_activation_audit") != 3) {
            throw new IllegalStateException("controlled migration did not end at the signed primary policy");
        }
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("schemaVersion", "open-04-001-controlled-migration-result-v0.1");
        output.put("completedStepsAtStart", startStep);
        output.put("steps", results);
        output.put("finalState", finalState);
        output.put("policyVersionCount", count(jdbc, "agent_security_policy_version"));
        output.put("activationAuditCount", count(jdbc, "agent_security_policy_activation_audit"));
        output.put("rollbackExercisePassed", true);
        System.out.println(mapper.writeValueAsString(output));
    }

    static int determineStartStep(JdbcTemplate jdbc, String primaryDigest, String drillDigest) {
        int activeCount = count(jdbc, "agent_security_policy_active");
        int versionCount = count(jdbc, "agent_security_policy_version");
        int auditCount = count(jdbc, "agent_security_policy_activation_audit");
        if (activeCount == 0 && versionCount == 0 && auditCount == 0) {
            return 0;
        }
        if (activeCount != 1) {
            throw new IllegalStateException("active policy state is not a recoverable DR-04-045 state");
        }
        Map<String, Object> state = jdbc.queryForMap("""
                SELECT policy_digest AS policyDigest, policy_epoch AS policyEpoch, state_version AS stateVersion
                  FROM agent_security_policy_active WHERE scope='GLOBAL'
                """);
        String digest = String.valueOf(state.get("policyDigest"));
        long epoch = ((Number) state.get("policyEpoch")).longValue();
        long stateVersion = ((Number) state.get("stateVersion")).longValue();
        if (primaryDigest.equals(digest) && epoch == 1 && stateVersion == 1
                && versionCount == 1 && auditCount == 1) {
            return 1;
        }
        if (drillDigest.equals(digest) && epoch == 2 && stateVersion == 2
                && versionCount == 2 && auditCount == 2) {
            return 2;
        }
        if (primaryDigest.equals(digest) && epoch == 3 && stateVersion == 3
                && versionCount == 2 && auditCount == 3) {
            return 3;
        }
        throw new IllegalStateException("database state does not match an exact recoverable DR-04-045 checkpoint");
    }

    private static int count(JdbcTemplate jdbc, String table) {
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
        return count == null ? -1 : count;
    }

    private static Path resolveInside(Path root, String relative) {
        Path path = Path.of(relative);
        if (path.isAbsolute() || relative.contains("\\")
                || !relative.equals(path.normalize().toString().replace('\\', '/'))) {
            throw new IllegalArgumentException("path must be canonical and repository-relative");
        }
        Path resolved = root.resolve(path).normalize();
        if (!resolved.startsWith(root)) {
            throw new IllegalArgumentException("path escapes repository root");
        }
        return resolved;
    }

    private static Map<String, String> parse(String[] args) {
        Map<String, String> result = new LinkedHashMap<>();
        for (int index = 0; index < args.length; index += 2) {
            if (index + 1 >= args.length || !args[index].startsWith("--")) {
                throw new IllegalArgumentException("arguments must be --name value pairs");
            }
            if (result.putIfAbsent(args[index].substring(2), args[index + 1]) != null) {
                throw new IllegalArgumentException("duplicate argument: " + args[index]);
            }
        }
        return result;
    }

    private static String require(Map<String, String> values, String key) {
        String value = values.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing --" + key);
        }
        return value;
    }

    private record PolicyPayload(String version, String schema, String payload) {
    }
}
