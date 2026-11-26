#Requires -Version 5.1
<#
.SYNOPSIS
    Organizes DEAD CHANNEL 13 root MP4 renders into masters/ and archive/ without deleting files.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$OutputJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = $PSScriptRoot
}
Set-Location -Path $ScriptDir
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

$RequiredDirs = @(
    'masters',
    'archive\ep01_acts',
    'archive\ep02_acts',
    'archive\v1_v2_showcases',
    'publish\thumbnails',
    'publish\shorts',
    'ep03'
)

foreach ($relDir in $RequiredDirs) {
    $fullDir = Join-Path -Path $ProjectRoot -ChildPath $relDir
    if (-not (Test-Path -LiteralPath $fullDir)) {
        if ($PSCmdlet.ShouldProcess($fullDir, 'Create directory')) {
            $null = New-Item -ItemType Directory -Path $fullDir -Force
        }
    }
}

$FileRouting = [ordered]@{
    'DEAD_CHANNEL_13_EP01_FULL_PILOT_JP_SUB.mp4'       = @{ Category = 'masters'; Dest = 'masters\DEAD_CHANNEL_13_EP01_FULL_PILOT_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP01_FULL_PILOT_EN_DUB.mp4'       = @{ Category = 'masters'; Dest = 'masters\DEAD_CHANNEL_13_EP01_FULL_PILOT_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP02_FULL_EPISODE_JP_SUB.mp4'     = @{ Category = 'masters'; Dest = 'masters\DEAD_CHANNEL_13_EP02_FULL_EPISODE_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP02_FULL_EPISODE_EN_DUB.mp4'     = @{ Category = 'masters'; Dest = 'masters\DEAD_CHANNEL_13_EP02_FULL_EPISODE_EN_DUB.mp4' }

    'DEAD_CHANNEL_13_EP01_COLD_OPEN_EN_DUB.mp4'        = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_COLD_OPEN_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP01_COLD_OPEN_JP_SUB.mp4'        = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_COLD_OPEN_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACT2_EN_DUB.mp4'             = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACT2_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACT2_JP_SUB.mp4'             = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACT2_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACT3_EN_DUB.mp4'             = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACT3_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACT3_JP_SUB.mp4'             = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACT3_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACT4_EN_DUB.mp4'             = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACT4_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACT4_JP_SUB.mp4'             = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACT4_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACTS_1_2_EN_DUB.mp4'         = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACTS_1_2_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACTS_1_2_JP_SUB.mp4'         = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACTS_1_2_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACTS_1_3_EN_DUB.mp4'         = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACTS_1_3_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP01_ACTS_1_3_JP_SUB.mp4'         = @{ Category = 'archive_ep01_acts'; Dest = 'archive\ep01_acts\DEAD_CHANNEL_13_EP01_ACTS_1_3_JP_SUB.mp4' }

    'DEAD_CHANNEL_13_EP02_ACT1_EN_DUB.mp4'             = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACT1_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACT1_JP_SUB.mp4'             = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACT1_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACT2_EN_DUB.mp4'             = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACT2_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACT2_JP_SUB.mp4'             = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACT2_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACT3_EN_DUB.mp4'             = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACT3_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACT3_JP_SUB.mp4'             = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACT3_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACTS_1_2_EN_DUB.mp4'         = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACTS_1_2_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_EP02_ACTS_1_2_JP_SUB.mp4'         = @{ Category = 'archive_ep02_acts'; Dest = 'archive\ep02_acts\DEAD_CHANNEL_13_EP02_ACTS_1_2_JP_SUB.mp4' }

    'DEAD_CHANNEL_13_Directors_Cut_Master.mp4'         = @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_Directors_Cut_Master.mp4' }
    'DEAD_CHANNEL_13_EN_DUB.mp4'                       = @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_JP_SUB.mp4'                       = @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_OPTION1_SAKUGA_SPEEDUP_JP_SUB.mp4'= @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_OPTION1_SAKUGA_SPEEDUP_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_OPTION2_SAKUGA_REBUILD_JP_SUB.mp4'= @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_OPTION2_SAKUGA_REBUILD_JP_SUB.mp4' }
    'DEAD_CHANNEL_13_Rain_on_the_Glass.mp4'            = @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_Rain_on_the_Glass.mp4' }
    'DEAD_CHANNEL_13_V2_DEFINITIVE_EN_DUB.mp4'         = @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_V2_DEFINITIVE_EN_DUB.mp4' }
    'DEAD_CHANNEL_13_V2_DEFINITIVE_JP_SUB.mp4'         = @{ Category = 'archive_v1_v2_showcases'; Dest = 'archive\v1_v2_showcases\DEAD_CHANNEL_13_V2_DEFINITIVE_JP_SUB.mp4' }
}

$Records = New-Object 'System.Collections.Generic.List[object]'

foreach ($fileName in $FileRouting.Keys) {
    $entry = $FileRouting[$fileName]
    $srcPath = Join-Path -Path $ProjectRoot -ChildPath $fileName
    $dstRel = [string]$entry.Dest
    $dstPath = Join-Path -Path $ProjectRoot -ChildPath $dstRel
    $status = 'Missing'

    if (Test-Path -LiteralPath $srcPath) {
        if (-not (Test-Path -LiteralPath $dstPath)) {
            if ($PSCmdlet.ShouldProcess($srcPath, "Move to $dstRel")) {
                Move-Item -LiteralPath $srcPath -Destination $dstPath -Force
                $status = 'Moved'
            }
        }
        else {
            $status = 'ConflictBothExist'
        }
    }
    elseif (Test-Path -LiteralPath $dstPath) {
        $status = 'AlreadyInDestination'
    }

    $sizeBytes = 0
    if (Test-Path -LiteralPath $dstPath) {
        $item = Get-Item -LiteralPath $dstPath
        $sizeBytes = [long]$item.Length
    }
    elseif (Test-Path -LiteralPath $srcPath) {
        $item = Get-Item -LiteralPath $srcPath
        $sizeBytes = [long]$item.Length
    }

    $Records.Add([PSCustomObject]@{
        SourceName              = $fileName
        DestinationRelativePath = $dstRel
        Category                = [string]$entry.Category
        Status                  = $status
        SizeBytes               = $sizeBytes
    })
}

$RemainingRootMp4s = @(Get-ChildItem -LiteralPath $ProjectRoot -Filter '*.mp4' -File)
$MastersMp4s = @(Get-ChildItem -LiteralPath (Join-Path -Path $ProjectRoot -ChildPath 'masters') -Filter '*.mp4' -File)
$ArchiveMp4s = @(Get-ChildItem -LiteralPath (Join-Path -Path $ProjectRoot -ChildPath 'archive') -Filter '*.mp4' -File -Recurse)

$RecordArray = $Records.ToArray()

$ManifestObj = [ordered]@{
    generatedAt         = (Get-Date).ToString('o')
    projectRoot         = $ProjectRoot
    rootMp4Count        = @($RemainingRootMp4s).Count
    mastersMp4Count     = @($MastersMp4s).Count
    archiveMp4Count     = @($ArchiveMp4s).Count
    trackedTotalCount   = $Records.Count
    preservedDirs       = @('frames', 'frames_ep1', 'frames_ep2', 'frames_v2', 'videos', 'videos_ep1', 'videos_ep2', 'videos_v2')
    files               = $RecordArray
}

$ManifestPath = Join-Path -Path $ProjectRoot -ChildPath 'FOLDER_MANIFEST.json'
if ($PSCmdlet.ShouldProcess($ManifestPath, 'Write FOLDER_MANIFEST.json')) {
    $jsonText = ($ManifestObj | ConvertTo-Json -Depth 6) + "`n"
    [System.IO.File]::WriteAllText($ManifestPath, $jsonText, [System.Text.UTF8Encoding]::new($false))
}

$ResultObj = [PSCustomObject]@{
    Status          = 'Success'
    ProjectRoot     = $ProjectRoot
    ManifestPath    = $ManifestPath
    RootMp4Count    = @($RemainingRootMp4s).Count
    MastersMp4Count = @($MastersMp4s).Count
    ArchiveMp4Count = @($ArchiveMp4s).Count
    MovedNowCount   = @($RecordArray | Where-Object { $_.Status -eq 'Moved' }).Count
    AlreadyCount    = @($RecordArray | Where-Object { $_.Status -eq 'AlreadyInDestination' }).Count
}

if ($OutputJson) {
    $ResultObj | ConvertTo-Json -Depth 4
}
else {
    $ResultObj
}
