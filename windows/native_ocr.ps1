param([Parameter(Mandatory=$true)][string]$ImagePath, [Parameter(Mandatory=$true)][string]$OutputPath, [int]$CropLeft, [int]$CropTop, [int]$CropWidth, [int]$CropHeight, [ValidateRange(2,3)][int]$Scale=2)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Wait-WinRT($Operation, [Type]$ResultType) {
    $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}
# Restrict OCR to the table, enlarge 2x, convert red text via green-channel grayscale.
Add-Type -AssemblyName System.Drawing
$source = [Drawing.Bitmap]::FromFile($ImagePath)
$preparedPath = Join-Path (Split-Path $OutputPath) 'holdings-grid-ocr.png'
$prepared = New-Object Drawing.Bitmap(($CropWidth*$Scale),($CropHeight*$Scale))
$graphics = [Drawing.Graphics]::FromImage($prepared)
$attributes = New-Object Drawing.Imaging.ImageAttributes
try {
    $matrix = New-Object Drawing.Imaging.ColorMatrix
    $matrix.Matrix00=0; $matrix.Matrix01=0; $matrix.Matrix02=0
    $matrix.Matrix10=1; $matrix.Matrix11=1; $matrix.Matrix12=1
    $matrix.Matrix20=0; $matrix.Matrix21=0; $matrix.Matrix22=0
    $attributes.SetColorMatrix($matrix)
    $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $destination = New-Object Drawing.Rectangle(0,0,($CropWidth*$Scale),($CropHeight*$Scale))
    $graphics.DrawImage($source,$destination,$CropLeft,$CropTop,$CropWidth,$CropHeight,[Drawing.GraphicsUnit]::Pixel,$attributes)
    $prepared.Save($preparedPath,[Drawing.Imaging.ImageFormat]::Png)
} finally {
    $attributes.Dispose(); $graphics.Dispose(); $prepared.Dispose(); $source.Dispose()
}
$ImagePath = $preparedPath
$file = Wait-WinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Wait-WinRT ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$bitmap = $null
try {
    $decoder = Wait-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Wait-WinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) { throw 'No installed OCR language engine' }
    $result = Wait-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = @($result.Lines | ForEach-Object {
        [ordered]@{ words = @($_.Words | ForEach-Object {
            [ordered]@{ text=$_.Text; left=$_.BoundingRect.X; top=$_.BoundingRect.Y;
                width=$_.BoundingRect.Width; height=$_.BoundingRect.Height }
        }) }
    })
    [ordered]@{ language=$engine.RecognizerLanguage.LanguageTag; scale=$Scale; origin=@($CropLeft,$CropTop); lines=$lines } |
        ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath
    [ordered]@{ status='recognized'; language=$engine.RecognizerLanguage.LanguageTag; line_count=$lines.Count } |
        ConvertTo-Json -Compress
} finally {
    if ($null -ne $bitmap) { $bitmap.Dispose() }
    $stream.Dispose()
}
