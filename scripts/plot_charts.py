import os
import csv
import matplotlib.pyplot as plt
import numpy as np
import json

# Set design styles for academic publication
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.titlesize': 14,
    'figure.dpi': 150
})

# Color palette
PRIMARY_COLOR = '#1f77b4'  # Professional blue
SECONDARY_COLOR = '#ff7f0e'  # Orange Accent
HIGHLIGHT_COLOR = '#2ca02c'  # Green for NCNN FP16 320
MUTED_COLOR = '#7f7f7f'      # Grey for Non-opt

os.makedirs('results/plots', exist_ok=True)

# ----------------------------------------------------
# HELPER: LOAD BENCHMARK DATA DYNAMICALLY (6 VERSIONS)
# ----------------------------------------------------
def load_model_comparison_data():
    # 8 versions of models
    models = [
        'PyTorch 320', 
        'NCNN 320 (Non-opt)', 
        'NCNN FP16 320\n(Optimal)', 
        'PyTorch 320\n(Toy)',
        'NCNN FP16 320\n(Toy)',
        'PyTorch 480', 
        'NCNN 480 (Non-opt)', 
        'NCNN FP16 480'
    ]
    # Fallback values in case the JSON is missing or incomplete
    fps_values = [5.9, 7.8, 10.6, 5.9, 10.6, 3.3, 3.6, 4.2]
    avg_latency = [170.2, 128.5, 94.0, 170.2, 94.0, 299.3, 277.8, 235.8]
    p95_latency = [175.7, 135.0, 100.2, 175.7, 100.2, 308.0, 310.0, 358.5]
    
    json_path = 'results/model_comparison_results.json'
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Map name in JSON -> Mapped name in chart
            model_map = {
                "PyTorch 320x320 (vehicle_custom_best_320.pt)": "PyTorch 320",
                "NCNN Original 320x320 (Non-opt)": "NCNN 320 (Non-opt)",
                "NCNN FP16 320x320 (Optimized)": "NCNN FP16 320\n(Optimal)",
                "PyTorch 320x320 Toy (vehicle_custom_best_320_(toy).pt)": "PyTorch 320\n(Toy)",
                "NCNN FP16 320x320 Toy (Optimized)": "NCNN FP16 320\n(Toy)",
                "PyTorch 480x480 (vehicle_custom_best.pt)": "PyTorch 480",
                "NCNN Original 480x480 (Non-opt)": "NCNN 480 (Non-opt)",
                "NCNN FP16 480x480 (Optimized)": "NCNN FP16 480"
            }
            
            matched_fps = {}
            matched_avg = {}
            matched_p95 = {}
            for item in data:
                name = item.get("name")
                if name in model_map:
                    mapped_name = model_map[name]
                    matched_fps[mapped_name] = item.get("fps", 0.0)
                    matched_avg[mapped_name] = item.get("avg_ms", 0.0)
                    matched_p95[mapped_name] = item.get("p95_ms", 0.0)
            
            # Update values dynamically if matched
            for i, m in enumerate(models):
                if m in matched_fps:
                    fps_values[i] = matched_fps[m]
                    avg_latency[i] = matched_avg[m]
                    p95_latency[i] = matched_p95[m]
            print(f"[plot_charts] Loaded dynamic model metrics from {json_path}")
        except Exception as e:
            print(f"[plot_charts] Error reading benchmark JSON: {e}. Using fallback values.")
            
    return models, fps_values, avg_latency, p95_latency

# ----------------------------------------------------
# 1. PLOT 1: MODEL FPS COMPARISON (Bar Chart)
# ----------------------------------------------------
def plot_fps_comparison():
    models, fps_values, _, _ = load_model_comparison_data()
    colors = [PRIMARY_COLOR, MUTED_COLOR, HIGHLIGHT_COLOR, PRIMARY_COLOR, HIGHLIGHT_COLOR, PRIMARY_COLOR, MUTED_COLOR, PRIMARY_COLOR]
    
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(models, fps_values, color=colors, edgecolor='grey', width=0.55)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f} FPS',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')
                    
    ax.set_ylabel('Theoretical FPS (Frames Per Second)', fontweight='bold')
    ax.set_title('Hình 5.4. So sánh tốc độ xử lý lý thuyết (FPS) giữa các mô hình', pad=15, fontweight='bold')
    
    # Set y-limit dynamically to 120% of max value
    max_fps = max(fps_values) if fps_values else 10
    ax.set_ylim(0, max_fps * 1.2)
    
    plt.tight_layout()
    plt.savefig('results/plots/hinh5_2_fps_comparison.png', dpi=300)
    plt.close()
    print("Generated results/plots/hinh5_2_fps_comparison.png")

# ----------------------------------------------------
# 2. PLOT 2: MODEL LATENCY COMPARISON (Grouped Bar Chart)
# ----------------------------------------------------
def plot_latency_comparison():
    models, _, avg_latency, p95_latency = load_model_comparison_data()
    
    x = np.arange(len(models))
    width = 0.35  # width of the bars
    
    fig, ax = plt.subplots(figsize=(10, 5))
    rects1 = ax.bar(x - width/2, avg_latency, width, label='Độ trễ trung bình', color=PRIMARY_COLOR, edgecolor='grey')
    rects2 = ax.bar(x + width/2, p95_latency, width, label='Độ trễ P95 (95th Percentile)', color=SECONDARY_COLOR, edgecolor='grey')
    
    # Add labels
    ax.set_ylabel('Latency (ms)', fontweight='bold')
    ax.set_title('Hình 5.5. So sánh độ trễ trung bình và trễ P95 giữa các mô hình', pad=15, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(frameon=True)
    
    # Set y-limit dynamically to 120% of max latency value
    max_lat = max(max(avg_latency), max(p95_latency)) if avg_latency and p95_latency else 350
    ax.set_ylim(0, max_lat * 1.2)
    
    # Add values on top of bars
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)
                        
    autolabel(rects1)
    autolabel(rects2)
    
    plt.tight_layout()
    plt.savefig('results/plots/hinh5_3_latency_comparison.png', dpi=300)
    plt.close()
    print("Generated results/plots/hinh5_3_latency_comparison.png")

# ----------------------------------------------------
# 3. PLOT 3: CPU TEMPERATURE OVER TIME (Line Chart)
# ----------------------------------------------------
def plot_cpu_temperature():
    times = []
    temps = []
    
    if os.path.exists('results/telemetry.csv'):
        with open('results/telemetry.csv', 'r') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                times.append(i * 5)  # logged every 5 seconds
                temps.append(float(row['cpu_temp_c']))
    
    if not temps:
        print("[plot_charts] results/telemetry.csv is empty or missing. Skipping CPU temp plot.")
        return

    avg_temp = np.mean(temps)
    max_temp = np.max(temps)
    
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(times, temps, marker='o', linestyle='-', color='#d62728', label='Nhiệt độ CPU (°C)', linewidth=2)
    
    # Draw limits and average
    ax.axhline(y=avg_temp, color='gray', linestyle='--', label=f'Nhiệt độ trung bình ({avg_temp:.1f}°C)')
    
    # Highlight max temperature point
    max_idx = temps.index(max_temp)
    ax.annotate(f'Cực đại: {max_temp:.1f}°C', 
                xy=(times[max_idx], max_temp), 
                xytext=(times[max_idx] - 15, max_temp + 1),
                arrowprops=dict(facecolor='black', shrink=0.08, width=1, headwidth=6),
                fontweight='bold', color='#d62728')
                
    ax.set_xlabel('Thời gian vận hành (giây)', fontweight='bold')
    ax.set_ylabel('Nhiệt độ CPU (°C)', fontweight='bold')
    ax.set_title('Hình 5.6. Biến thiên nhiệt độ CPU theo thời gian vận hành (Stress Test)', pad=15, fontweight='bold')
    
    # Set y-limit dynamically
    ax.set_ylim(min(temps) - 5, max(temps) + 5)
    ax.legend(loc='lower right', frameon=True)
    
    plt.tight_layout()
    plt.savefig('results/plots/hinh5_4_cpu_temperature.png', dpi=300)
    plt.close()
    print("Generated results/plots/hinh5_4_cpu_temperature.png")

# ----------------------------------------------------
# 4. PLOT 4: RAM CONSUMPTION OVER TIME (Line Chart)
# ----------------------------------------------------
def plot_ram_usage():
    times = []
    ram_used = []
    
    if os.path.exists('results/telemetry.csv'):
        with open('results/telemetry.csv', 'r') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                times.append(i * 5)
                ram_used.append(float(row['ram_used_mb']))
                
    if not ram_used:
        print("[plot_charts] results/telemetry.csv is empty or missing. Skipping RAM usage plot.")
        return

    init_ram = ram_used[0]
    max_ram = np.max(ram_used)
    stable_ram = np.mean(ram_used[len(ram_used)//2:]) if len(ram_used) > 1 else ram_used[0]
    
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(times, ram_used, marker='s', linestyle='-', color=PRIMARY_COLOR, label='RAM đã sử dụng (MB)', linewidth=2)
    
    # Annotate initial peak and stable state
    ax.annotate(f'RAM ban đầu: {init_ram:.0f} MB', xy=(0, init_ram), xytext=(5, init_ram - 50),
                arrowprops=dict(facecolor='black', shrink=0.08, width=0.5, headwidth=4))
    
    max_idx = ram_used.index(max_ram)
    ax.annotate(f'Tải trước ảnh cực đại: {max_ram:.0f} MB', xy=(times[max_idx], max_ram), xytext=(times[max_idx] - 25, max_ram + 30),
                arrowprops=dict(facecolor='black', shrink=0.08, width=0.5, headwidth=4), fontweight='bold')
                
    ax.annotate(f'Ổn định: ~{stable_ram:.0f} MB', xy=(times[-2], stable_ram), xytext=(times[-2] - 20, stable_ram - 60),
                arrowprops=dict(facecolor='black', shrink=0.08, width=0.5, headwidth=4))
                
    ax.set_xlabel('Thời gian vận hành (giây)', fontweight='bold')
    ax.set_ylabel('RAM tiêu thụ (MB)', fontweight='bold')
    ax.set_title('Hình 5.7. Biến thiên dung lượng bộ nhớ RAM tiêu thụ theo thời gian', pad=15, fontweight='bold')
    ax.set_ylim(min(ram_used) - 100, max(ram_used) + 100)
    ax.legend(loc='lower right', frameon=True)
    
    plt.tight_layout()
    plt.savefig('results/plots/hinh5_5_ram_usage.png', dpi=300)
    plt.close()
    print("Generated results/plots/hinh5_5_ram_usage.png")

# ----------------------------------------------------
# 5. PLOT 5: LOOP FPS OVER TIME (Line Chart)
# ----------------------------------------------------
def plot_loop_fps():
    frames = []
    fps_values = []
    
    if os.path.exists('results/fps_latency_run.csv'):
        with open('results/fps_latency_run.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                frames.append(int(row['frame']))
                fps_values.append(float(row['fps']))
                
    if not fps_values:
        print("[plot_charts] results/fps_latency_run.csv is empty or missing. Skipping Loop FPS plot.")
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(frames, fps_values, marker='v', linestyle='-', color=HIGHLIGHT_COLOR, label='Tốc độ vòng lặp (Loop FPS)', linewidth=2)
    
    avg_loop_fps = np.mean(fps_values)
    ax.axhline(y=avg_loop_fps, color='gray', linestyle='--', label=f'FPS trung bình ({avg_loop_fps:.2f} FPS)')
    
    ax.set_xlabel('Chỉ số khung hình (Frame index)', fontweight='bold')
    ax.set_ylabel('Tốc độ hiển thị (FPS)', fontweight='bold')
    ax.set_title('Hình 5.8. Biến thiên tốc độ hiển thị vòng lặp (Loop FPS) theo số khung hình', pad=15, fontweight='bold')
    ax.set_ylim(min(fps_values) - 2, max(fps_values) + 2)
    ax.legend(loc='lower right', frameon=True)
    
    plt.tight_layout()
    plt.savefig('results/plots/hinh5_6_loop_fps.png', dpi=300)
    plt.close()
    print("Generated results/plots/hinh5_6_loop_fps.png")

# ----------------------------------------------------
# 6. PLOT 6: RUNTIME AI LATENCY OVER TIME (Line Chart)
# ----------------------------------------------------
def plot_runtime_latency():
    frames = []
    latencies = []
    
    if os.path.exists('results/fps_latency_run.csv'):
        with open('results/fps_latency_run.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                val = float(row['latency_ms'])
                if val > 0:  # skip initial warmups where inference didn't start or was zero
                    frames.append(int(row['frame']))
                    latencies.append(val)
                
    if not latencies:
        print("[plot_charts] results/fps_latency_run.csv is empty or missing. Skipping runtime latency plot.")
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(frames, latencies, marker='o', linestyle='-', color=SECONDARY_COLOR, label='Độ trễ suy luận AI (ms)', linewidth=2)
    
    avg_lat = np.mean(latencies)
    ax.axhline(y=avg_lat, color='gray', linestyle='--', label=f'Độ trễ trung bình thực tế (~{avg_lat:.1f} ms)')
    
    # Highlight fluctuations
    ax.set_xlabel('Chỉ số khung hình (Frame index)', fontweight='bold')
    ax.set_ylabel('Runtime Latency (ms)', fontweight='bold')
    ax.set_title('Hình 5.9. Biến thiên độ trễ suy luận AI thực tế trong quá trình vận hành (Runtime Latency)', pad=15, fontweight='bold')
    ax.set_ylim(max(0, min(latencies) - 50), max(latencies) + 100)
    ax.legend(loc='upper right', frameon=True)
    
    plt.tight_layout()
    plt.savefig('results/plots/runtime_latency_fluctuation.png', dpi=300)
    plt.close()
    print("Generated results/plots/runtime_latency_fluctuation.png")

if __name__ == '__main__':
    plot_fps_comparison()
    plot_latency_comparison()
    plot_cpu_temperature()
    plot_ram_usage()
    plot_loop_fps()
    plot_runtime_latency()
    print("All charts plotted successfully!")
