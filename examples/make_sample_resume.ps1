# Builds examples\sample-resume.docx with Word: a fictional resume in the format the tools expect.
$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot 'sample-resume.docx'
$lines = @(
    @('Jane Doe', 'title'),
    @('Junior Full-Stack Developer', 'sub'),
    @('Tel Aviv, Israel | jane@example.com | linkedin.com/in/jane-doe | github.com/jane-doe', 'sub'),
    @('Professional Summary', 'h'),
    @('Junior full-stack developer with a BSc in Computer Science and hands-on experience building web apps with Node.js, React and SQL.', 'p'),
    @('Technical Skills', 'h'),
    @('Languages: JavaScript, TypeScript, Python, SQL, HTML5, CSS', 'b'),
    @('Frameworks: Node.js, Express, React, REST API', 'b'),
    @('Tools/Platforms: Git, GitHub, Docker, AWS, Linux', 'b'),
    @('Work Experience', 'h'),
    @('Junior Developer | Example Ltd. | 2024 - Present', 'bold'),
    @('Built internal dashboards with React and a Node.js REST API backed by PostgreSQL.', 'b'),
    @('Education', 'h'),
    @('BSc Computer Science | Example University', 'bold')
)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Add()
    $sel = $word.Selection
    foreach ($l in $lines) {
        $text, $kind = $l
        $sel.Font.Reset(); $sel.ParagraphFormat.Reset()
        switch ($kind) {
            'title' { $sel.Font.Bold = 1; $sel.Font.Size = 16; $sel.ParagraphFormat.Alignment = 1 }
            'sub'   { $sel.Font.Size = 10; $sel.ParagraphFormat.Alignment = 1 }
            'h'     { $sel.Font.Bold = 1; $sel.Font.Underline = 1; $sel.Font.Size = 11; $sel.ParagraphFormat.SpaceBefore = 8 }
            'bold'  { $sel.Font.Bold = 1; $sel.Font.Size = 10 }
            default { $sel.Font.Size = 10 }
        }
        if ($kind -eq 'b') { $sel.Range.ListFormat.ApplyBulletDefault() }
        $sel.TypeText($text)
        $sel.TypeParagraph()
        if ($kind -eq 'b') { $sel.Range.ListFormat.RemoveNumbers() }
    }
    # Word stamps the Windows user as author; the sample must not carry anyone's name.
    $doc.RemovePersonalInformation = $true
    $doc.SaveAs2($out, 16)   # 16 = wdFormatDocumentDefault (.docx)
    $doc.Close()
} finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
Write-Host "Saved $out"
