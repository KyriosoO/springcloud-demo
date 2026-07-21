package com.dylan.esquery.api.model.document;

/** 传输层可见的 operation safe metadata。 */
public record DocumentSearchOperationMetadata(
        String requestCorrelationId,
        String operationId,
        String operationType,
        long absoluteDeadlineEpochMilli,
        String registrationIdentity,
        ResourceLimitBindingDto resourceLimit) {
    public DocumentSearchOperationMetadata {
        if(requestCorrelationId==null||requestCorrelationId.isBlank()||operationId==null||operationId.isBlank()
                ||operationType==null||operationType.isBlank()||absoluteDeadlineEpochMilli<=0
                ||registrationIdentity==null||registrationIdentity.isBlank()||resourceLimit==null){
            throw new IllegalArgumentException("document search operation metadata incomplete");
        }
    }
}
