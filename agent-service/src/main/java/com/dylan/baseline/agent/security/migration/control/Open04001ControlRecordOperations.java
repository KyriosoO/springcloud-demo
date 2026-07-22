package com.dylan.baseline.agent.security.migration.control;

import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.List;

/** 将签名记录中的精确操作序列投影为验证请求；操作人必须来自实际执行输入。 */
final class Open04001ControlRecordOperations {

    private Open04001ControlRecordOperations() {
    }

    static List<ApprovalVerificationRequest> verificationRequests(JsonNode record, String actorRefDigest) {
        JsonNode operations = record.get("policyOperations");
        String approvalRef = record.path("recordId").textValue();
        List<ApprovalVerificationRequest> requests = new ArrayList<>();
        if (operations == null || !operations.isArray()) {
            throw new IllegalArgumentException("control record policyOperations must be an array");
        }
        for (JsonNode operation : operations) {
            JsonNode from = operation.get("fromPolicyDigest");
            requests.add(new ApprovalVerificationRequest(
                    approvalRef,
                    operation.path("operation").textValue(),
                    from == null || from.isNull() ? null : from.textValue(),
                    operation.path("toPolicyDigest").textValue(),
                    operation.path("changeClass").textValue(),
                    operation.path("expectedStateVersion").longValue(),
                    actorRefDigest));
        }
        return List.copyOf(requests);
    }
}
