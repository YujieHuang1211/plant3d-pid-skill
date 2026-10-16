# 符号测量：在一个 AutoCAD 会话里新建图、同步样式、画出测量 spec、导出 info（块参照外框）
#   powershell.exe -File scan_symbols.ps1 -Project <Project.xml> -Spec <SYM-MEASURE.json> -Dwg <图名.dwg> -InfoOut <输出 info.log> [-StyleCfg <qmz_stylecfg.json>]
param([string]$Project, [string]$Spec, [string]$Dwg, [string]$InfoOut,
      [string]$StyleCfg = 'E:\05p_id图绘制中心\_PidBot\specs\qmz_stylecfg.json')
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path 'E:\05p_id图绘制中心\_PidBot\scripts' 'pidbot.psm1') -DisableNameChecking
$log = 'E:\05p_id图绘制中心\_PidBot\logs'
function Run($verb, $arg, $t = 300) { $r = Invoke-PbVerb $verb $arg $t; $r | Select-String '错误|失败|完成：' | ForEach-Object { "  [$verb] $($_.Line)" } }
"启动 AutoCAD"
Start-Acad $Project | Select-String '就绪|当前项目|启动耗时' | ForEach-Object { "  $($_.Line)" }
Run newdwg $Dwg 120
Run syncstyles $StyleCfg 300
Run draw $Spec 600
Run regen x 120
$null = Invoke-PbVerb info x 300
Copy-Item "$log\info.log" $InfoOut -Force
Run qsave x 60
$null = Stop-Acad
"完成：info 写到 $InfoOut"
