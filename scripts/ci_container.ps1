param(
    [string]$Image = "property-rental:life-os",
    [string]$ArtifactDirectory = "artifacts/container"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $ArtifactDirectory | Out-Null

docker build --tag $Image .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/container_smoke.py --image $Image
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$inspectPath = Join-Path $ArtifactDirectory "image-inspect.json"
$historyPath = Join-Path $ArtifactDirectory "image-history.txt"
$ociArchivePath = Join-Path $ArtifactDirectory "image-oci.tar"

docker image inspect $Image | Out-File -Encoding utf8 $inspectPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker image history --no-trunc $Image | Out-File -Encoding utf8 $historyPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$builderName = "property-rental-oci-$PID"
docker buildx create --name $builderName --driver docker-container --use --bootstrap | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
try {
    docker buildx build --builder $builderName --output "type=oci,dest=$ociArchivePath" .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    docker buildx rm $builderName | Out-Null
}

$uncompressedBytes = [int64](docker image inspect --format '{{.Size}}' $Image)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$compressedArchivePath = "$ociArchivePath.gz"
$gzipCommand = Get-Command gzip -ErrorAction SilentlyContinue
if ($gzipCommand) {
    gzip -f $ociArchivePath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    $inputStream = [System.IO.File]::OpenRead($ociArchivePath)
    $outputStream = [System.IO.File]::Create($compressedArchivePath)
    try {
        $gzipStream = [System.IO.Compression.GZipStream]::new(
            $outputStream,
            [System.IO.Compression.CompressionLevel]::Optimal
        )
        try {
            $inputStream.CopyTo($gzipStream)
        } finally {
            $gzipStream.Dispose()
        }
    } finally {
        $inputStream.Dispose()
        $outputStream.Dispose()
    }
    Remove-Item -LiteralPath $ociArchivePath
}
$compressedBytes = (Get-Item $compressedArchivePath).Length

$sizes = [ordered]@{
    image = $Image
    uncompressed_bytes = $uncompressedBytes
    compressed_archive_bytes = $compressedBytes
}
$sizes | ConvertTo-Json | Tee-Object -FilePath (Join-Path $ArtifactDirectory "image-sizes.json")
