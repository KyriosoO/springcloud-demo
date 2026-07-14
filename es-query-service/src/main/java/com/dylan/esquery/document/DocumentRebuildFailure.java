package com.dylan.esquery.document;

/** 只携带 safe failure code，原始异常不得持久化到 task。 */
public final class DocumentRebuildFailure extends RuntimeException {
    private final String failureCode;
    public DocumentRebuildFailure(String failureCode) { super(failureCode); this.failureCode = failureCode; }
    public DocumentRebuildFailure(String failureCode, Throwable cause) { super(failureCode, cause); this.failureCode = failureCode; }
    public String failureCode() { return failureCode; }
}
