function Test-EmployeeLiveSensitiveText {
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

    # 用户名按独立标记匹配，避免把 com.dylan 或 com/dylan 等构建坐标误判为身份泄漏。
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

function Get-EmployeeLiveSafeFailureCode {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$Text
    )

    $match = [Regex]::Match($Text, 'employee\.live_[a-z0-9_]+(?::[A-Za-z0-9_]+)?')
    if (-not $match.Success) {
        return 'employee.live_integration_failed'
    }
    $parts = $match.Value.Split(':', 2)
    $allowedCodes = @(
        'employee.live_case_failed',
        'employee.live_endpoint_scope_invalid',
        'employee.live_env_missing',
        'employee.live_probe_exception_type_error',
        'employee.live_probe_http_error',
        'employee.live_probe_runtime_error',
        'employee.live_probe_timeout',
        'employee.live_probe_unexpected_error',
        'employee.live_probe_value_error',
        'employee.live_projection_failed',
        'employee.live_response_too_large',
        'employee.live_visibility_invalid'
    )
    if ($allowedCodes -notcontains $parts[0]) {
        return 'employee.live_integration_failed'
    }
    if ($parts.Count -eq 1) {
        return $parts[0]
    }
    $allowedSuffixes = @(
        'adminPrimary', 'adminSecondary', 'viewer', 'unknownRole',
        'missingToken', 'malformedToken', 'serviceToken'
    )
    if ($parts[0] -in @('employee.live_case_failed', 'employee.live_projection_failed') -and
            $allowedSuffixes -contains $parts[1]) {
        return $match.Value
    }
    return $parts[0]
}

function Remove-EmployeeLiveJUnitHostMetadata {
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
