from mpi4py import MPI
import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import sys
import queue
import os

# MPI setup
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Check if we are running directly with Python or via mpiexec
RUNNING_WITH_MPI = size > 1

# Simulation parameters
SIM_DELAY = 0.5
TIME_QUANTUM = 2
NUM_CPUS = 3  # Default number of CPUs when not using MPI

# Tutorial tooltips - educational content
TOOLTIPS = {
    "round_robin": "Round Robin assigns each process a fixed time slice (quantum) in a circular order.\nIf a process doesn't complete in its time slice, it's moved to the back of the queue.",
    "fcfs": "First-Come-First-Served executes processes in the order they arrive.\nSimple but can lead to convoy effect where short processes wait for long ones.",
    "cpu": "CPUs execute the processes assigned by the scheduler.\nModern computers typically have multiple CPU cores.",
    "process": "A process is a program in execution. Each process needs CPU time to complete.\nThe burst time is how long a process needs the CPU.",
    "scheduler": "The scheduler decides which process runs on which CPU and when.\nIt aims to maximize efficiency while being fair to all processes.",
    "gantt": "A Gantt chart shows which processes run on each CPU over time.\nIt helps visualize how the scheduling algorithm allocates CPU time."
}

class Process:
    def __init__(self, pid, burst, arrival):
        self.pid = pid
        self.burst = burst
        self.arrival = arrival
        self.remaining = burst
        self.start_time = None
        self.end_time = None
        self.color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        # Ensure the color is not too light
        r, g, b = int(self.color[1:3], 16), int(self.color[3:5], 16), int(self.color[5:7], 16)
        if r + g + b > 550:  # If color is too light
            self.color = "#{:06x}".format(random.randint(0, 0x7FFFFF))  # Darker color
        # Track execution history for Gantt chart
        self.execution_history = []  # List of (cpu_id, start_time, end_time)

class SchedulerApp:
    def __init__(self, master):
        self.master = master
        master.title("MPI OS Scheduler Simulation")
        master.geometry("900x750")
        master.configure(bg="#f0f0f0")
        
        # Set the theme
        style = ttk.Style()
        style.theme_use('clam')
        
        # Create notebook for tabs (main view and visualization)
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Main tab
        main_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(main_frame, text="Simulation")
        
        # Visualization tab
        self.viz_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.viz_frame, text="Visualization")
        
        # Tutorial mode variables
        self.tutorial_mode = tk.BooleanVar(value=False)
        self.current_tooltip = None
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(header_frame, text="OS Process Scheduler Simulation", 
                 font=("Helvetica", 18, "bold")).pack(side=tk.LEFT)
        
        # Mode indicators
        mode_frame = ttk.Frame(header_frame)
        mode_frame.pack(side=tk.RIGHT)
        
        mode_text = "MPI Mode (Multi-Process)" if RUNNING_WITH_MPI else "Simulation Mode (Single-Process)"
        self.mode_label = ttk.Label(mode_frame, text=mode_text, 
                           font=("Helvetica", 12), foreground="blue")
        self.mode_label.pack(side=tk.TOP, padx=10)
        
        # Tutorial mode checkbox
        tutorial_check = ttk.Checkbutton(mode_frame, text="Tutorial Mode", 
                                        variable=self.tutorial_mode,
                                        command=self.toggle_tutorial_mode)
        tutorial_check.pack(side=tk.BOTTOM, padx=10)
        
        # Time display
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(fill=tk.X, pady=5)
        
        self.time_label = ttk.Label(time_frame, text="Time: 0", font=("Helvetica", 14))
        self.time_label.pack(side=tk.LEFT)
        self.register_tooltip(self.time_label, "Simulation time in arbitrary units.")
        
        # Algorithm selection
        algo_frame = ttk.Frame(main_frame)
        algo_frame.pack(fill=tk.X, pady=5)
        
        algo_label = ttk.Label(algo_frame, text="Scheduling Algorithm:", 
                 font=("Helvetica", 12))
        algo_label.pack(side=tk.LEFT, padx=5)
        self.register_tooltip(algo_label, TOOLTIPS["scheduler"])
                 
        self.algo_var = tk.StringVar(value="Round Robin")
        algo_combo = ttk.Combobox(algo_frame, textvariable=self.algo_var, 
                                 values=["Round Robin", "FCFS"], state="readonly", width=15)
        algo_combo.pack(side=tk.LEFT, padx=5)
        self.register_tooltip(algo_combo, "Select which scheduling algorithm to use")
        
        # CPU visualization
        self.cpu_frame = ttk.LabelFrame(main_frame, text="CPU Status", padding=10)
        self.cpu_frame.pack(fill=tk.X, pady=10, padx=5)
        self.register_tooltip(self.cpu_frame, TOOLTIPS["cpu"])
        
        self.cpu_labels = []
        self.progress_bars = []
        
        cpu_count = size - 1 if RUNNING_WITH_MPI else NUM_CPUS
        
        for cpu_id in range(1, cpu_count + 1):
            cpu_row = ttk.Frame(self.cpu_frame)
            cpu_row.pack(fill=tk.X, pady=5)
            
            cpu_label = ttk.Label(cpu_row, text=f"CPU {cpu_id}:", width=10)
            cpu_label.pack(side=tk.LEFT, padx=5)
            
            lbl = ttk.Label(cpu_row, text="Idle", width=20)
            lbl.pack(side=tk.LEFT, padx=5)
            self.cpu_labels.append(lbl)
            
            progress = ttk.Progressbar(cpu_row, orient=tk.HORIZONTAL, length=300, mode='determinate')
            progress.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self.progress_bars.append(progress)
        
        # Process queue visualization
        self.queue_frame = ttk.LabelFrame(main_frame, text="Process Queue", padding=10)
        self.queue_frame.pack(fill=tk.X, pady=10, padx=5)
        self.register_tooltip(self.queue_frame, TOOLTIPS["process"])
        
        self.queue_canvas = tk.Canvas(self.queue_frame, height=80, bg="white", highlightthickness=1, highlightbackground="gray")
        self.queue_canvas.pack(fill=tk.X, expand=True)
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.register_tooltip(self.start_btn, "Start the scheduling simulation")
        
        self.pause_btn = ttk.Button(control_frame, text="Pause", command=self.pause, width=15)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.register_tooltip(self.pause_btn, "Pause the simulation")
        
        self.resume_btn = ttk.Button(control_frame, text="Resume", command=self.resume, width=15)
        self.resume_btn.pack(side=tk.LEFT, padx=5)
        self.register_tooltip(self.resume_btn, "Resume the paused simulation")
        
        self.reset_btn = ttk.Button(control_frame, text="Reset", command=self.reset, width=15)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        self.register_tooltip(self.reset_btn, "Reset the simulation with new random processes")
        
        # Log box with title
        log_frame = ttk.LabelFrame(main_frame, text="Simulation Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        # Add scrollbar to log box
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_box = tk.Text(log_frame, height=10, wrap=tk.WORD, yscrollcommand=log_scroll.set)
        self.log_box.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        log_scroll.config(command=self.log_box.yview)
        
        # Setup visualization tab
        self.setup_visualization_tab()
        
        # Thread control
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.stop_event = threading.Event()
        self.scheduler_thread = None
        
        # Processes and queue
        self.processes = []
        self.queue_proc = queue.deque()
        self.simulation_history = []  # Track all process executions for visualization
        self.clock = 0
        
        master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log("System ready. Click 'Start' to begin simulation.")
        
        # If tutorial mode is on by default, show a welcome message
        if self.tutorial_mode.get():
            self.show_tutorial_message("Welcome to OS Scheduler Simulation! Hover over elements to learn more.")
    
    def setup_visualization_tab(self):
        """Setup the visualization tab with Gantt chart and timeline view"""
        # Create frames for visualization components
        viz_top_frame = ttk.Frame(self.viz_frame)
        viz_top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(viz_top_frame, text="Execution Visualization", 
                 font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
                 
        # Gantt chart
        gantt_frame = ttk.LabelFrame(self.viz_frame, text="Gantt Chart", padding=10)
        gantt_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        self.register_tooltip(gantt_frame, TOOLTIPS["gantt"])
        
        # Create canvas with scrollbar for Gantt chart
        gantt_scroll_x = ttk.Scrollbar(gantt_frame, orient="horizontal")
        gantt_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        gantt_scroll_y = ttk.Scrollbar(gantt_frame)
        gantt_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.gantt_canvas = tk.Canvas(gantt_frame, bg="white", 
                                     xscrollcommand=gantt_scroll_x.set,
                                     yscrollcommand=gantt_scroll_y.set,
                                     highlightthickness=1, highlightbackground="gray")
        self.gantt_canvas.pack(fill=tk.BOTH, expand=True)
        
        gantt_scroll_x.config(command=self.gantt_canvas.xview)
        gantt_scroll_y.config(command=self.gantt_canvas.yview)
        
        # Timeline view
        timeline_frame = ttk.LabelFrame(self.viz_frame, text="Process Timeline", padding=10)
        timeline_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        # Create canvas with scrollbar for timeline
        timeline_scroll_x = ttk.Scrollbar(timeline_frame, orient="horizontal")
        timeline_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        timeline_scroll_y = ttk.Scrollbar(timeline_frame)
        timeline_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.timeline_canvas = tk.Canvas(timeline_frame, bg="white", 
                                       xscrollcommand=timeline_scroll_x.set,
                                       yscrollcommand=timeline_scroll_y.set,
                                       highlightthickness=1, highlightbackground="gray")
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True)
        
        timeline_scroll_x.config(command=self.timeline_canvas.xview)
        timeline_scroll_y.config(command=self.timeline_canvas.yview)
    
    def register_tooltip(self, widget, text):
        """Register a tooltip for a widget"""
        widget.bind("<Enter>", lambda event, t=text: self.show_tooltip(event, t))
        widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event, text):
        """Show tooltip when mouse hovers over a widget"""
        if not self.tutorial_mode.get():
            return
            
        x, y, _, _ = event.widget.bbox("insert")
        x += event.widget.winfo_rootx() + 25
        y += event.widget.winfo_rooty() + 25
        
        # Creates a toplevel window
        self.hide_tooltip()  # Hide existing tooltip if any
        self.current_tooltip = tk.Toplevel(event.widget)
        
        # Leaves only the label and removes the app window
        self.current_tooltip.wm_overrideredirect(True)
        self.current_tooltip.wm_geometry(f"+{x}+{y}")
        
        label = ttk.Label(self.current_tooltip, text=text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Arial", "9", "normal"), wraplength=300)
        label.pack(padx=2, pady=2)
    
    def hide_tooltip(self, event=None):
        """Hide the tooltip"""
        if self.current_tooltip:
            self.current_tooltip.destroy()
            self.current_tooltip = None
    
    def toggle_tutorial_mode(self):
        """Toggle tutorial mode on/off"""
        if self.tutorial_mode.get():
            self.show_tutorial_message("Tutorial mode enabled. Hover over elements to see explanations.")
        else:
            self.hide_tooltip()
            self.log("Tutorial mode disabled.")
    
    def show_tutorial_message(self, message):
        """Show a tutorial message in the log"""
        self.log(f"📚 TUTORIAL: {message}")
    
    def log(self, msg):
        """Add a message to the log box"""
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
    
    def start(self):
        """Start the simulation"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.log("⚠️ Simulation already running.")
            return
        self.stop_event.clear()
        self.pause_event.set()
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.log("▶️ Simulation started.")
        
        if self.tutorial_mode.get():
            algo = self.algo_var.get()
            if algo == "Round Robin":
                self.show_tutorial_message(TOOLTIPS["round_robin"])
            else:
                self.show_tutorial_message(TOOLTIPS["fcfs"])
    
    def pause(self):
        """Pause the simulation"""
        self.pause_event.clear()
        self.log("⏸️ Simulation paused.")
    
    def resume(self):
        """Resume the simulation"""
        self.pause_event.set()
        self.log("▶️ Simulation resumed.")
    
    def reset(self):
        """Reset the simulation"""
        self.stop_event.set()
        self.pause_event.set()
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
        
        # Reset CPU displays
        for i, lbl in enumerate(self.cpu_labels):
            lbl.config(text="Idle")
            self.progress_bars[i]['value'] = 0
        
        # Reset queue display
        self.queue_canvas.delete("all")
        
        # Reset visualization
        self.gantt_canvas.delete("all")
        self.timeline_canvas.delete("all")
        
        # Reset time and history
        self.clock = 0
        self.time_label.config(text="Time: 0")
        self.simulation_history = []
        
        self.log("🔄 Simulation reset. Ready to start again.")
    
    def update_queue_display(self):
        """Update the process queue visualization"""
        self.queue_canvas.delete("all")
        x_pos = 10
        y_pos = 40
        
        for i, proc in enumerate(self.queue_proc):
            width = 50
            height = 30
            
            # Draw process box
            self.queue_canvas.create_rectangle(
                x_pos, y_pos - height/2, 
                x_pos + width, y_pos + height/2, 
                fill=proc.color, outline="black")
            
            # Draw process text
            self.queue_canvas.create_text(
                x_pos + width/2, y_pos, 
                text=f"P{proc.pid}\n{proc.remaining}u", font=("Arial", 8))
            
            x_pos += width + 10
    
    def update_gantt_chart(self):
        """Update the Gantt chart with current execution history"""
        self.gantt_canvas.delete("all")
        
        # Set up chart dimensions and scaling
        cpu_count = size - 1 if RUNNING_WITH_MPI else NUM_CPUS
        cell_height = 40
        cell_width = 40
        time_width = 40
        header_height = 30
        
        # Adjust canvas scroll region based on clock time
        self.gantt_canvas.config(scrollregion=(0, 0, time_width + (self.clock + 1) * cell_width, 
                                              header_height + cpu_count * cell_height))
        
        # Draw time headers
        for t in range(self.clock + 1):
            self.gantt_canvas.create_rectangle(
                time_width + t * cell_width, 0,
                time_width + (t + 1) * cell_width, header_height,
                fill="lightgray", outline="gray")
            self.gantt_canvas.create_text(
                time_width + t * cell_width + cell_width/2, header_height/2,
                text=str(t), font=("Arial", 8))
        
        # Draw CPU labels
        for cpu in range(cpu_count):
            self.gantt_canvas.create_rectangle(
                0, header_height + cpu * cell_height,
                time_width, header_height + (cpu + 1) * cell_height,
                fill="lightgray", outline="gray")
            self.gantt_canvas.create_text(
                time_width/2, header_height + cpu * cell_height + cell_height/2,
                text=f"CPU {cpu+1}", font=("Arial", 10))
        
        # Draw process executions
        for proc in self.processes:
            for cpu_id, start, end in proc.execution_history:
                cpu_idx = cpu_id - 1  # Convert to 0-based index
                
                # Draw process execution block
                self.gantt_canvas.create_rectangle(
                    time_width + start * cell_width, header_height + cpu_idx * cell_height,
                    time_width + end * cell_width, header_height + (cpu_idx + 1) * cell_height,
                    fill=proc.color, outline="black")
                
                # Draw process ID
                self.gantt_canvas.create_text(
                    time_width + (start + (end - start)/2) * cell_width,
                    header_height + cpu_idx * cell_height + cell_height/2,
                    text=f"P{proc.pid}", font=("Arial", 9, "bold"))
    
    def update_timeline(self):
        """Update the timeline view with process start and end times"""
        self.timeline_canvas.delete("all")
        
        # Set up timeline dimensions
        proc_height = 30
        time_width = 40
        header_height = 30
        cell_width = 40
        
        # Adjust canvas scroll region
        self.timeline_canvas.config(scrollregion=(0, 0, time_width + (self.clock + 1) * cell_width,
                                                header_height + len(self.processes) * proc_height))
        
        # Draw time headers
        for t in range(self.clock + 1):
            self.timeline_canvas.create_rectangle(
                time_width + t * cell_width, 0,
                time_width + (t + 1) * cell_width, header_height,
                fill="lightgray", outline="gray")
            self.timeline_canvas.create_text(
                time_width + t * cell_width + cell_width/2, header_height/2,
                text=str(t), font=("Arial", 8))
        
        # Draw process labels and execution spans
        for i, proc in enumerate(sorted(self.processes, key=lambda p: p.pid)):
            # Process label
            self.timeline_canvas.create_rectangle(
                0, header_height + i * proc_height,
                time_width, header_height + (i + 1) * proc_height,
                fill="lightgray", outline="gray")
            self.timeline_canvas.create_text(
                time_width/2, header_height + i * proc_height + proc_height/2,
                text=f"P{proc.pid}", font=("Arial", 10))
            
            # Process execution spans
            for cpu_id, start, end in proc.execution_history:
                # Draw execution rectangle
                self.timeline_canvas.create_rectangle(
                    time_width + start * cell_width, 
                    header_height + i * proc_height + 5,
                    time_width + end * cell_width, 
                    header_height + (i + 1) * proc_height - 5,
                    fill=proc.color, outline="black")
                
                # Add CPU identifier in the block
                self.timeline_canvas.create_text(
                    time_width + (start + (end - start)/2) * cell_width,
                    header_height + i * proc_height + proc_height/2,
                    text=f"CPU{cpu_id}", font=("Arial", 8))
    
    def simulate_process(self, cpu_id, proc, run_time):
        """Simulate a process running on a CPU (non-MPI mode)"""
        # Record start time for this execution
        proc_start_time = self.clock
        
        # Update progress bar for visual feedback
        self.progress_bars[cpu_id-1]['maximum'] = run_time
        self.progress_bars[cpu_id-1]['value'] = 0
        
        for t in range(run_time):
            if self.stop_event.is_set():
                return 0
            
            self.pause_event.wait()
            time.sleep(SIM_DELAY)
            self.progress_bars[cpu_id-1]['value'] = t + 1
            self.master.update()
        
        # Record end time for this execution
        proc_end_time = self.clock + run_time
        proc.execution_history.append((cpu_id, proc_start_time, proc_end_time))
        
        return max(0, proc.remaining - run_time)
    
    def run_scheduler(self):
        """Run the scheduling simulation"""
        algo = self.algo_var.get()
        self.log(f"🧠 Using {algo} scheduling algorithm")
        
        # Generate processes
        self.processes = [Process(i+1, random.randint(4, 10), i) for i in range(6)]
        self.queue_proc = queue.deque(sorted(self.processes, key=lambda p: p.arrival))
        self.clock = 0
        
        # Log process details
        self.log("📋 Process Queue:")
        for proc in self.processes:
            self.log(f"   Process {proc.pid}: Burst={proc.burst}u, Arrival={proc.arrival}")
        
        self.log("📦 Scheduling started.")
        
        cpu_count = size - 1 if RUNNING_WITH_MPI else NUM_CPUS
        
        while self.queue_proc and not self.stop_event.is_set():
            self.pause_event.wait()
            
            # For FCFS, keep sorted by arrival
            if algo == "FCFS":
                self.queue_proc = queue.deque(sorted(self.queue_proc, key=lambda p: p.arrival))
            
            self.update_queue_display()
            
            for cpu_id in range(1, cpu_count + 1):
                if not self.queue_proc or self.stop_event.is_set():
                    break
                
                proc = self.queue_proc.popleft()
                run = min(TIME_QUANTUM, proc.remaining) if algo == "Round Robin" else proc.remaining
                
                # Mark process start time if first execution
                if proc.start_time is None:
                    proc.start_time = self.clock
                
                # Update GUI
                self.cpu_labels[cpu_id-1].config(text=f"Running P{proc.pid} ({run}u)")
                self.log(f"🟢 CPU {cpu_id} → P{proc.pid} | Remaining: {proc.remaining}u | Run: {run}u")
                
                # Execute process
                if RUNNING_WITH_MPI:
                    # Send to worker process via MPI
                    comm.send((proc.pid, run), dest=cpu_id)
                    
                    # Record start time for this execution
                    proc_start_time = self.clock
                    
                    time.sleep(SIM_DELAY * run)
                    
                    try:
                        remaining = comm.recv(source=cpu_id, timeout=5)
                    except Exception as e:
                        self.log(f"❌ MPI Recv error: {e}")
                        remaining = max(0, proc.remaining - run)
                    
                    # Record end time and update history
                    proc_end_time = self.clock + run
                    proc.execution_history.append((cpu_id, proc_start_time, proc_end_time))
                else:
                    # Simulate process execution
                    remaining = self.simulate_process(cpu_id, proc, run)
                
                # Update process and clock
                self.clock += run
                proc.remaining = remaining
                self.time_label.config(text=f"Time: {self.clock}")
                
                # If process completed, record end time
                if remaining == 0:
                    proc.end_time = self.clock
                
                # Reset CPU display
                self.cpu_labels[cpu_id-1].config(text="Idle")
                self.progress_bars[cpu_id-1]['value'] = 0
                
                # Handle process completion or re-queue
                if remaining > 0:
                    if algo == "Round Robin":
                        self.queue_proc.append(proc)
                        self.log(f"🔄 P{proc.pid} re-queued with {remaining}u remaining")
                else:
                    self.log(f"✅ P{proc.pid} completed execution")
                
                # Update visualization
                self.update_gantt_chart()
                self.update_timeline()
            
            # Small delay between CPU assignment cycles
            time.sleep(0.2)
        
        if not self.stop_event.is_set():
            self.time_label.config(text=f"Time: {self.clock} (Complete)")
            self.log("🏁 All processes completed.")
            
            # Show completion statistics
            self.show_completion_stats()
    
    def show_completion_stats(self):
        """Calculate and display process completion statistics"""
        completed_processes = [p for p in self.processes if p.end_time is not None]
        
        if not completed_processes:
            return
            
        total_turnaround = sum(p.end_time - p.arrival for p in completed_processes)
        avg_turnaround = total_turnaround / len(completed_processes)
        
        total_waiting = sum(p.end_time - p.arrival - p.burst for p in completed_processes)
        avg_waiting = total_waiting / len(completed_processes)
        
        self.log("\n📊 Performance Statistics:")
        self.log(f"   Average Turnaround Time: {avg_turnaround:.2f} time units")
        self.log(f"   Average Waiting Time: {avg_waiting:.2f} time units")
        
        if self.tutorial_mode.get():
            self.show_tutorial_message("Turnaround time = time from arrival to completion. Waiting time = time spent waiting for CPU.")
    
    def on_close(self):
        """Handle window close event"""
        self.stop_event.set()
        self.pause_event.set()
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
        
        if RUNNING_WITH_MPI:
            for i in range(1, size):
                comm.send(("STOP", 0), dest=i)
        
        self.master.destroy()
        sys.exit(0)

def worker_loop():
    while True:
        pid, burst = comm.recv(source=0)
        if pid == "STOP":
            break
        time.sleep(SIM_DELAY * burst)
        remaining = max(0, burst - TIME_QUANTUM)
        comm.send(remaining, dest=0)

# Create a batch file to run with MPI
def create_mpi_launcher():
    batch_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_simulation.bat")
    with open(batch_path, "w") as f:
        f.write('@echo off\n')
        f.write('echo Starting MPI OS Scheduler Simulation...\n')
        f.write('echo.\n')
        f.write('if exist "C:\\Program Files\\Microsoft MPI\\Bin\\mpiexec.exe" (\n')
        f.write('    "C:\\Program Files\\Microsoft MPI\\Bin\\mpiexec.exe" -n 4 python "%~dp0os_mpi.py"\n')
        f.write(') else (\n')
        f.write('    echo Microsoft MPI not found. Install it first.\n')
        f.write('    echo You can download it from: https://www.microsoft.com/en-us/download/details.aspx?id=57467\n')
        f.write('    echo.\n')
        f.write('    pause\n')
        f.write(')\n')
    print(f"Created batch file: {batch_path}")
    print("Double-click on 'run_simulation.bat' to run the simulation with MPI.")

if rank == 0:
    if not RUNNING_WITH_MPI:
        print("Running in simulation mode (single process).")
        print("For true parallel execution, run with: mpiexec -n 4 python os_mpi.py")
        create_mpi_launcher()
    
    root = tk.Tk()
    app = SchedulerApp(root)
    root.mainloop()
else:
    try:
        worker_loop()
    except Exception as e:
        print(f"Worker {rank} encountered an error: {e}")
        sys.exit(1)
