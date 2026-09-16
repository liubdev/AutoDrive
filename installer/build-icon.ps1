# Convert the transparent brand master into a multi-resolution Windows icon.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$root = Split-Path -Parent $PSScriptRoot
$source = [Drawing.Bitmap]::FromFile((Join-Path $root 'ui\assets\brand_logo.png'))
$sizes = @(16, 24, 32, 48, 64, 128, 256)
$images = [Collections.Generic.List[byte[]]]::new()
try {
    foreach ($size in $sizes) {
        $bitmap = [Drawing.Bitmap]::new($size, $size, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $stream = [IO.MemoryStream]::new()
        try {
            $graphics.Clear([Drawing.Color]::Transparent)
            $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $width = [single]($size * 0.94)
            $height = [single]($width * 900 / 1080)
            $destination = [Drawing.RectangleF]::new(($size-$width)/2, ($size-$height)/2, $width, $height)
            $graphics.DrawImage($source, $destination, [Drawing.RectangleF]::new(80, 200, 1080, 900), [Drawing.GraphicsUnit]::Pixel)
            $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
            $images.Add($stream.ToArray())
        } finally {
            $stream.Dispose()
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
    $output = [IO.MemoryStream]::new()
    $writer = [IO.BinaryWriter]::new($output)
    try {
        $writer.Write([uint16]0)
        $writer.Write([uint16]1)
        $writer.Write([uint16]$sizes.Count)
        $offset = 6 + 16 * $sizes.Count
        for ($i = 0; $i -lt $sizes.Count; $i++) {
            $edge = if ($sizes[$i] -eq 256) { 0 } else { $sizes[$i] }
            $writer.Write([byte]$edge)
            $writer.Write([byte]$edge)
            $writer.Write([uint16]0)
            $writer.Write([uint16]1)
            $writer.Write([uint16]32)
            $writer.Write([uint32]$images[$i].Length)
            $writer.Write([uint32]$offset)
            $offset += $images[$i].Length
        }
        foreach ($bytes in $images) { $writer.Write($bytes) }
        [IO.File]::WriteAllBytes((Join-Path $root 'icon.ico'), $output.ToArray())
    } finally {
        $writer.Dispose()
        $output.Dispose()
    }
} finally { $source.Dispose() }
Write-Host 'icon.ico generated: 16, 24, 32, 48, 64, 128, 256px'
