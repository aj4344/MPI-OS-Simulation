@echo off
echo Starting MPI OS Scheduler Simulation...
echo.
if exist "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe" (
    "C:\Program Files\Microsoft MPI\Bin\mpiexec.exe" -n 4 python "%~dp0os_mpi.py"
) else (
    echo Microsoft MPI not found. Install it first.
    echo You can download it from: https://www.microsoft.com/en-us/download/details.aspx?id=57467
    echo.
    pause
)
