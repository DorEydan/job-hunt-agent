param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$Pdf
)
# Exports a .docx to PDF with the installed Microsoft Word (keeps the exact layout).
# Macros are force-disabled and the file is opened read-only, without conversion prompts.
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3   # msoAutomationSecurityForceDisable
try {
    # Open(FileName, ConfirmConversions, ReadOnly, AddToRecentFiles)
    $doc = $word.Documents.Open($Docx, $false, $true, $false)
    $doc.ExportAsFixedFormat($Pdf, 17)   # 17 = wdExportFormatPDF
    $doc.Close([ref]0)
}
finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
