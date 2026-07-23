package com.dylan.esquery.document.governance.emergency;

public record DocumentEvidenceSignature(String algorithm,String keyId,String keyVersion,String signatureBase64Url) {}
