# Organize local files without invalidating absolute paths in build caches.
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$localRoot = Join-Path $projectRoot '.local'
$groups = [ordered]@{
    builds = @('build', 'build-android-check', 'build-android-native', 'build-android-native-x86_64', 'build-android-package', 'build-android-package-x86_64', 'build-retrotouch')
    dependencies = @('build-android-deps')
    private = @('Call of Duty Deluxe Edition', 'decomp', 'ghidra_projects', 'recomp_out')
}
foreach ($group in $groups.Keys) {
    $destinationRoot = Join-Path $localRoot $group
    New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
    foreach ($name in $groups[$group]) {
        $source = [IO.Path]::GetFullPath((Join-Path $projectRoot $name))
        $destination = [IO.Path]::GetFullPath((Join-Path $destinationRoot $name))
        foreach ($candidate in @($source, $destination)) {
            if (-not $candidate.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Path outside workspace: $candidate"
            }
        }
        if (-not (Test-Path -LiteralPath $source)) { continue }
        $existing = Get-Item -LiteralPath $source -Force
        if ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            if ([IO.Path]::GetFullPath([string]$existing.Target) -ne $destination) {
                throw "Unexpected junction target: $source"
            }
            continue
        }
        if (Test-Path -LiteralPath $destination) {
            $targetItem = Get-Item -LiteralPath $destination -Force
            if (($targetItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
                [IO.Path]::GetFullPath([string]$targetItem.Target) -eq $source) { continue }
            throw "Destination already exists: $destination"
        }
        try {
            Move-Item -LiteralPath $source -Destination $destination
        } catch {
            Write-Warning "Kept locked directory at its original path: $source ($($_.Exception.Message))"
            New-Item -ItemType Junction -Path $destination -Target $source | Out-Null
            continue
        }
        try {
            New-Item -ItemType Junction -Path $source -Target $destination | Out-Null
        } catch {
            Move-Item -LiteralPath $destination -Destination $source
            throw
        }
        # Hide compatibility aliases in Explorer; actual folders live under .local.
        $alias = Get-Item -LiteralPath $source -Force
        $alias.Attributes = $alias.Attributes -bor [IO.FileAttributes]::Hidden
        Write-Output "$name -> .local/$group/$name"
    }
}
foreach ($name in @('references', 'toolchains', 'downloads', 'profiles')) {
    New-Item -ItemType Directory -Path (Join-Path $localRoot $name) -Force | Out-Null
}
