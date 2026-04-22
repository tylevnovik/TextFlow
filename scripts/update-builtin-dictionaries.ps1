$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$targetRoot = Join-Path $root "services\python-engine\app\builtin_dictionary_sources"

$downloads = @(
  @{
    RelativePath = "stopwords-iso\stopwords-zh.json"
    Url = "https://raw.githubusercontent.com/stopwords-iso/stopwords-zh/master/stopwords-zh.json"
  },
  @{
    RelativePath = "stopwords-iso\stopwords-en.json"
    Url = "https://raw.githubusercontent.com/stopwords-iso/stopwords-en/master/stopwords-en.json"
  },
  @{
    RelativePath = "THUOCL\THUOCL_IT.txt"
    Url = "https://raw.githubusercontent.com/thunlp/THUOCL/master/data/THUOCL_IT.txt"
  },
  @{
    RelativePath = "THUOCL\THUOCL_caijing.txt"
    Url = "https://raw.githubusercontent.com/thunlp/THUOCL/master/data/THUOCL_caijing.txt"
  },
  @{
    RelativePath = "THUOCL\THUOCL_medical.txt"
    Url = "https://raw.githubusercontent.com/thunlp/THUOCL/master/data/THUOCL_medical.txt"
  },
  @{
    RelativePath = "THUOCL\THUOCL_chengyu.txt"
    Url = "https://raw.githubusercontent.com/thunlp/THUOCL/master/data/THUOCL_chengyu.txt"
  },
  @{
    RelativePath = "THUOCL\THUOCL_lishimingren.txt"
    Url = "https://raw.githubusercontent.com/thunlp/THUOCL/master/data/THUOCL_lishimingren.txt"
  },
  @{
    RelativePath = "THUOCL\THUOCL_diming.txt"
    Url = "https://raw.githubusercontent.com/thunlp/THUOCL/master/data/THUOCL_diming.txt"
  },
  @{
    RelativePath = "OpenCC\TSPhrases.txt"
    Url = "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TSPhrases.txt"
  },
  @{
    RelativePath = "OpenCC\TWPhrasesRev.txt"
    Url = "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TWPhrasesRev.txt"
  },
  @{
    RelativePath = "misspell\words.go"
    Url = "https://raw.githubusercontent.com/client9/misspell/master/words.go"
  }
)

New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null

$manifestEntries = @()

foreach ($download in $downloads) {
  $targetPath = Join-Path $targetRoot $download.RelativePath
  $targetDir = Split-Path -Parent $targetPath
  New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

  Write-Host "Downloading $($download.Url)"
  Invoke-WebRequest -Uri $download.Url -OutFile $targetPath -UseBasicParsing

  $item = Get-Item $targetPath
  $manifestEntries += [PSCustomObject]@{
    relative_path = ($download.RelativePath -replace "\\", "/")
    source_url = $download.Url
    size_bytes = $item.Length
    fetched_at = [DateTimeOffset]::UtcNow.ToString("o")
  }
}

$manifestPath = Join-Path $targetRoot "manifest.json"
$manifest = [PSCustomObject]@{
  generated_at = [DateTimeOffset]::UtcNow.ToString("o")
  files = $manifestEntries
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "Built-in dictionary snapshots updated under $targetRoot"
