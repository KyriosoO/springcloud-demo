package com.dylan.esquery.document.governance.management;
public record DocumentManagementErrorResponse(String contractVersion,DocumentManagementErrorCode code,String diagnosticId) {}
