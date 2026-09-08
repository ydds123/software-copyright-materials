# verify_code_docx_pages.ps1
# 程序鉴别材料 Word 渲染验证（v1.8）：总页数 + 每页非空代码行数
# 用法: pwsh -NoProfile -File verify_code_docx_pages.ps1 -Docx <path> [-ExpectPages 60] [-ExpectLines 50]
# 退出码: 0 通过 / 1 不达标 / 2 Word COM 不可用（调用方按环境跳过）

param(
    [Parameter(Mandatory=$true)][string]$Docx,
    [int]$ExpectPages = 60,
    [int]$ExpectLines = 50
)

[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if (-not (Test-Path $Docx)) {
    Write-Output "VERIFY_FAIL: docx 不存在: $Docx"
    exit 1
}

try {
    $word = New-Object -ComObject Word.Application
} catch {
    Write-Output "VERIFY_SKIP: Word COM 不可用，跳过渲染验证（非 Windows/无 Office 环境）"
    exit 2
}

$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, $false, $true)
} catch {
    Write-Output "VERIFY_FAIL: Word 无法打开 docx"
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    exit 1
}

$pages = $doc.ComputeStatistics(2)
$bad = @()
for ($p = 1; $p -le $pages; $p++) {
    $r1 = $doc.Range().GoTo(1, 1, $p)
    if ($p -lt $pages) {
        $r2 = $doc.Range().GoTo(1, 1, ($p + 1))
        $r = $doc.Range($r1.Start, $r2.Start)
    } else {
        $r = $doc.Range($r1.Start, $doc.Range().End)
    }
    $lines = ($r.Text -split "`r" | Where-Object { $_.Trim().Length -gt 0 }).Count
    if ($lines -ne $ExpectLines) {
        $bad += "第 $p 页: $lines 行"
    }
}

$doc.Close($false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null

if ($pages -ne $ExpectPages) {
    Write-Output "VERIFY_FAIL: 总页数 $pages ≠ 期望 $ExpectPages"
    exit 1
}
if ($bad.Count -gt 0) {
    Write-Output "VERIFY_FAIL: 每页代码行数不达标（期望 $ExpectLines 行/页）:"
    $bad | ForEach-Object { Write-Output "  $_" }
    exit 1
}
Write-Output "VERIFY_PASS: $pages 页 × 每页 $ExpectLines 行代码"
exit 0
