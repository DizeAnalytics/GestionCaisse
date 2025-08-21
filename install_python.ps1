# Script d'installation de Python pour Windows
Write-Host "Installation de Python 3.11 pour Windows..." -ForegroundColor Green

# URL de téléchargement de Python 3.11 (version stable)
$pythonUrl = "https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe"
$installerPath = "$env:TEMP\python-3.11.8-amd64.exe"

Write-Host "Téléchargement de Python 3.11.8..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath
    Write-Host "Téléchargement terminé avec succès!" -ForegroundColor Green
} catch {
    Write-Host "Erreur lors du téléchargement: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "Installation de Python..." -ForegroundColor Yellow
try {
    # Installation silencieuse avec ajout au PATH
    Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0" -Wait
    Write-Host "Installation terminée avec succès!" -ForegroundColor Green
} catch {
    Write-Host "Erreur lors de l'installation: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Nettoyage
Remove-Item $installerPath -Force

Write-Host "Python a été installé avec succès!" -ForegroundColor Green
Write-Host "Veuillez redémarrer votre terminal PowerShell pour que les changements prennent effet." -ForegroundColor Yellow
Write-Host "Ensuite, vous pourrez vérifier l'installation avec: python --version" -ForegroundColor Cyan
