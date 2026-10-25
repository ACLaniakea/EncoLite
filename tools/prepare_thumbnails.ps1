$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$root=Split-Path -Parent $PSScriptRoot
$destination=Join-Path $root 'ui\assets\thumbs'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach($source in Get-ChildItem (Join-Path $root 'ui\assets\models') -Filter '*.png') {
  $image=[System.Drawing.Image]::FromFile($source.FullName)
  try {
    foreach($size in @(26,32,39,52,56,70,84,112,140,168,224)) {
      $bitmap=[System.Drawing.Bitmap]::new($size,$size)
      $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
      try {
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $ratio=[Math]::Min($size/$image.Width,$size/$image.Height)
        $width=[int]($image.Width*$ratio);$height=[int]($image.Height*$ratio)
        $graphics.DrawImage($image,[int](($size-$width)/2),[int](($size-$height)/2),$width,$height)
        $bitmap.Save((Join-Path $destination ($source.BaseName+'-'+$size+'.png')),[System.Drawing.Imaging.ImageFormat]::Png)
      } finally {$graphics.Dispose();$bitmap.Dispose()}
    }
  } finally {$image.Dispose()}
}
