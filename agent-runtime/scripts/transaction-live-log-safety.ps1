function Test-TransactionLiveSensitiveText {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$Text,
        [object[]]$LiteralSensitiveValues,
        [string[]]$ExpectedPrincipals
    )

    foreach ($sensitive in $LiteralSensitiveValues) {
        if ($sensitive -and $Text.Contains([string]$sensitive)) {
            return $true
        }
    }

    $principalBoundary = '[\p{L}\p{N}_./\\-]'
    foreach ($principal in $ExpectedPrincipals) {
        if ([string]::IsNullOrWhiteSpace($principal)) {
            continue
        }
        $pattern = '(?i)(?<!' + $principalBoundary + ')' +
            [Regex]::Escape($principal) + '(?!' + $principalBoundary + ')'
        if ([Regex]::IsMatch($Text, $pattern, [Text.RegularExpressions.RegexOptions]::CultureInvariant)) {
            return $true
        }
    }
    return $false
}

function Remove-TransactionLiveJUnitHostMetadata {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$Text
    )

    try {
        [xml]$document = $Text
        foreach ($suite in @($document.SelectNodes('//testsuite[@hostname]'))) {
            $suite.RemoveAttribute('hostname')
        }
        return $document.OuterXml
    } catch {
        return $Text
    }
}

function Get-TransactionLiveSafeFailureCode {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$Text
    )

    $match = [Regex]::Match($Text, 'transaction\.live_[a-z0-9_]+(?::[A-Za-z0-9_]+)?')
    if (-not $match.Success) {
        $phasePatterns = [ordered]@{
            'Failed to load ApplicationContext' = 'transaction.live_context_failed'
            'APPLICATION FAILED TO START' = 'transaction.live_context_failed'
            'COMPILATION ERROR' = 'transaction.live_compile_failed'
            'There are test failures' = 'transaction.live_test_process_failed'
            'Tests run: 1, Failures: 0, Errors: 1' = 'transaction.live_test_process_failed'
            'Tests run: 1, Failures: 1' = 'transaction.live_test_process_failed'
        }
        foreach ($entry in $phasePatterns.GetEnumerator()) {
            if ($Text.Contains([string]$entry.Key)) {
                return [string]$entry.Value
            }
        }
        return 'transaction.live_integration_failed'
    }
    $parts = $match.Value.Split(':', 2)
    $allowed = @(
        'transaction.live_auth_build_failed',
        'transaction.live_auth_fixture_missing',
        'transaction.live_auth_fixture_not_local',
        'transaction.live_auth_process_exited',
        'transaction.live_auth_readiness_timeout',
        'transaction.live_assertion_failed',
        'transaction.live_bootstrap_failed',
        'transaction.live_call_count_invalid',
        'transaction.live_case_failed',
        'transaction.live_compile_failed',
        'transaction.live_context_failed',
        'transaction.live_endpoint_scope_invalid',
        'transaction.live_env_missing',
        'transaction.live_evidence_schema_invalid',
        'transaction.live_gateway_auth_failed',
        'transaction.live_gateway_build_failed',
        'transaction.live_gateway_forwarding_failed',
        'transaction.live_gateway_jar_missing',
        'transaction.live_gateway_process_exited',
        'transaction.live_gateway_readiness_timeout',
        'transaction.live_gateway_route_missing',
        'transaction.live_gateway_status_invalid',
        'transaction.live_gateway_contract_failed',
        'transaction.live_gateway_request_failed',
        'transaction.live_gateway_start_failed',
        'transaction.live_json_number_invalid',
        'transaction.live_io_failed',
        'transaction.live_java_failed',
        'transaction.live_login_failed',
        'transaction.live_metrics_missing',
        'transaction.live_metrics_write_failed',
        'transaction.live_probe_exception_type_error',
        'transaction.live_probe_http_error',
        'transaction.live_probe_runtime_error',
        'transaction.live_probe_timeout',
        'transaction.live_probe_unexpected_error',
        'transaction.live_probe_value_error',
        'transaction.live_probe_contract_failed',
        'transaction.live_python_probe_failed',
        'transaction.live_python_probe_timeout',
        'transaction.live_direct_contract_failed',
        'transaction.live_response_too_large',
        'transaction.live_test_process_failed',
        'transaction.live_token_missing'
    )
    if ($allowed -notcontains $parts[0]) {
        return 'transaction.live_integration_failed'
    }
    if ($parts.Count -eq 1) {
        return $parts[0]
    }
    $caseIds = @('adminPrimary', 'adminSecondary', 'viewer', 'unknownRole', 'missingToken', 'malformedToken', 'serviceToken')
    if ($parts[0] -eq 'transaction.live_case_failed' -and $caseIds -contains $parts[1]) {
        return $match.Value
    }
    return $parts[0]
}
