param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "demo", "prod")]
    [string]$Profile,

    [Parameter(Mandatory = $true)]
    [string[]]$RequiredKeys,

    [Parameter(Mandatory = $true)]
    [object]$AllowConfigValues
)

$ErrorActionPreference = "Stop"

function Convert-ToBooleanValue {
    param([object]$Value)
    if ($Value -is [bool]) {
        return $Value
    }
    switch ($Value.ToString().ToLowerInvariant()) {
        "true" { return $true }
        "1" { return $true }
        "false" { return $false }
        "0" { return $false }
        default {
            Write-Error "SECRET_ARGUMENT_INVALID name=AllowConfigValues"
            exit 3
        }
    }
}

$allowConfig = Convert-ToBooleanValue $AllowConfigValues
$normalizedRequiredKeys = @()
foreach ($item in $RequiredKeys) {
    foreach ($key in $item.Split(",")) {
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            $normalizedRequiredKeys += $key.Trim()
        }
    }
}

if ($Profile -eq "prod" -and $allowConfig) {
    Write-Error "SECRET_POLICY_VIOLATION profile=prod allowConfigValues=true"
    exit 2
}

$missing = @()
foreach ($key in $normalizedRequiredKeys) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {
        $missing += $key
    }
}

if ($missing.Count -gt 0) {
    Write-Error "SECRET_MISSING keys=$($missing -join ',')"
    exit 1
}

Write-Output "SECRET_INPUTS_OK profile=$Profile requiredKeys=$($normalizedRequiredKeys.Count)"
