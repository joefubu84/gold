param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

& python "$PSScriptRoot/qwen_cli.py" @ScriptArgs
