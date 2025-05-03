# MPI OS Scheduler Simulation

A visual simulation of operating system process scheduling using MPI (Message Passing Interface) to create multiple parallel processes that act as CPUs.

## Project Overview

This project demonstrates how different CPU scheduling algorithms work in a multi-core environment using real parallel processes. It provides an educational visualization of core operating system concepts including process scheduling, CPU utilization, and algorithm comparison.

## Features

- **True Parallel Processing**: Uses MPI to create actual parallel processes, not just a visual simulation
- **Multiple Scheduling Algorithms**:
  - Round Robin: Processes get a fixed time quantum (2 units) before returning to the queue
  - First-Come-First-Served (FCFS): Processes are executed in order of arrival
- **Interactive Visualization**:
  - Gantt chart showing CPU allocation over time
  - Process timeline view to track each process from start to completion
  - Real-time process queue visualization
- **Educational Tools**:
  - Tutorial mode with informative tooltips
  - Performance metrics calculation (average waiting time, turnaround time)
  - Detailed logging of scheduling decisions

## Requirements

- Python 3.6+
- Microsoft MPI (included as msmpisetup.exe)
- mpi4py (Python MPI library)
- tkinter (included with most Python installations)

## Installation

1. Install Microsoft MPI by running the included `msmpisetup.exe`
2. Install the required Python packages:
   ```
   pip install mpi4py
   ```

## Usage

### Option 1: Quick Start (Recommended)
Simply double-click the `run_simulation.bat` file to launch the simulation using MPI with 4 processes.

### Option 2: Manual Execution
Run the simulation using the MPI executor:
```
mpiexec -n 4 python os_mpi.py
```

### Option 3: Simulation Mode (No MPI)
Run directly with Python to use simulation mode (without true parallelism):
```
python os_mpi.py
```

## How It Works

1. **MPI Architecture**:
   - Process 0 (rank 0) acts as the scheduler/master
   - Processes 1-3 (ranks 1-3) function as worker CPUs
   - The master dispatches work via MPI messages
   - Workers report completion status back to the master

2. **User Interface**:
   - Main tab shows active CPU usage and process queue
   - Visualization tab displays Gantt chart and process timeline
   - Control buttons to start/pause/resume/reset the simulation

3. **Process Simulation**:
   - Random processes with different burst times are generated
   - Each process has a PID, burst time, and arrival time
   - Processes are scheduled according to the selected algorithm
   - The simulation shows real-time visualization of CPU allocation

## Project Structure

- `os_mpi.py` - Main simulation code
- `run_simulation.bat` - Batch file to easily run the simulation
- `msmpisetup.exe` - Microsoft MPI installer

## Credits

Developed by OS Creed Team from Modern College of Engineering, Pune (MCA Department):
- Abhijeet
- Krutika
- Hitesh
- Pratik

## License

This project is available for educational purposes.
