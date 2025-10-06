#!/usr/bin/env python3
"""
Simple plotting script for thread comparison results
"""

import csv
import matplotlib.pyplot as plt
import numpy as np

def load_data(csv_file):
    """Load data from CSV file"""
    champions = []
    skin_counts = []
    time_2 = []
    time_3 = []
    avg_skin_2 = []
    avg_skin_3 = []
    speedup = []
    degradation = []
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Skin_Count'] != 'ERROR':
                champions.append(row['Champion'])
                skin_counts.append(int(row['Skin_Count']))
                time_2.append(float(row['2_Threads_Total_Time']))
                time_3.append(float(row['3_Threads_Total_Time']))
                avg_skin_2.append(float(row['2_Threads_Avg_Skin_Time']))
                avg_skin_3.append(float(row['3_Threads_Avg_Skin_Time']))
                speedup.append(float(row['Speedup_2_to_3']))
                degradation.append(float(row['Performance_Degradation']))
    
    return champions, skin_counts, time_2, time_3, avg_skin_2, avg_skin_3, speedup, degradation

def create_plots(champions, skin_counts, time_2, time_3, avg_skin_2, avg_skin_3, speedup, degradation):
    """Create comprehensive plots"""
    
    # Set up the figure
    fig = plt.figure(figsize=(20, 16))
    
    # Convert to numpy arrays for easier manipulation
    champions = np.array(champions)
    skin_counts = np.array(skin_counts)
    time_2 = np.array(time_2)
    time_3 = np.array(time_3)
    avg_skin_2 = np.array(avg_skin_2)
    avg_skin_3 = np.array(avg_skin_3)
    speedup = np.array(speedup)
    degradation = np.array(degradation)
    
    # 1. Speedup Distribution
    ax1 = plt.subplot(3, 3, 1)
    ax1.hist(speedup, bins=20, alpha=0.7, edgecolor='black', color='skyblue')
    ax1.axvline(1.0, color='red', linestyle='--', linewidth=2, label='No improvement')
    ax1.set_xlabel('Speedup (2→3 threads)')
    ax1.set_ylabel('Number of Champions')
    ax1.set_title('Distribution of 2→3 Thread Speedup')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Performance Degradation Distribution
    ax2 = plt.subplot(3, 3, 2)
    ax2.hist(degradation, bins=20, alpha=0.7, edgecolor='black', color='orange')
    ax2.axvline(0, color='red', linestyle='--', linewidth=2, label='No degradation')
    ax2.set_xlabel('Performance Degradation (%)')
    ax2.set_ylabel('Number of Champions')
    ax2.set_title('Individual Skin Time Degradation (2→3 threads)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Speedup vs Skin Count
    ax3 = plt.subplot(3, 3, 3)
    scatter = ax3.scatter(skin_counts, speedup, c=degradation, 
                         cmap='RdYlGn', alpha=0.7, s=60)
    ax3.axhline(1.0, color='red', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Number of Skins')
    ax3.set_ylabel('Speedup (2→3 threads)')
    ax3.set_title('Speedup vs Skin Count\n(Color = Performance Degradation)')
    plt.colorbar(scatter, ax=ax3, label='Performance Degradation (%)')
    ax3.grid(True, alpha=0.3)
    
    # 4. Total Time Comparison (sorted by 2-thread time)
    ax4 = plt.subplot(3, 3, 4)
    sorted_indices = np.argsort(time_2)
    x_pos = np.arange(len(champions))
    width = 0.35
    
    ax4.bar(x_pos - width/2, time_2[sorted_indices], width, 
            label='2 Threads', alpha=0.8, color='lightgreen')
    ax4.bar(x_pos + width/2, time_3[sorted_indices], width, 
            label='3 Threads', alpha=0.8, color='orange')
    ax4.set_xlabel('Champions (sorted by 2-thread time)')
    ax4.set_ylabel('Total Time (seconds)')
    ax4.set_title('Total Time: 2 vs 3 Threads')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
    
    # 5. Average Skin Time Comparison (sorted by 2-thread time)
    ax5 = plt.subplot(3, 3, 5)
    ax5.bar(x_pos - width/2, avg_skin_2[sorted_indices], width, 
            label='2 Threads', alpha=0.8, color='skyblue')
    ax5.bar(x_pos + width/2, avg_skin_3[sorted_indices], width, 
            label='3 Threads', alpha=0.8, color='lightcoral')
    ax5.set_xlabel('Champions (sorted by 2-thread time)')
    ax5.set_ylabel('Average Skin Time (seconds)')
    ax5.set_title('Average Skin Time: 2 vs 3 Threads')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    ax5.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
    
    # 6. Worst Performers (Top 10 worst speedup)
    ax6 = plt.subplot(3, 3, 6)
    worst_indices = np.argsort(speedup)[:10]
    worst_champions = champions[worst_indices]
    worst_speedups = speedup[worst_indices]
    
    bars = ax6.bar(range(len(worst_champions)), worst_speedups, 
                   color='red', alpha=0.7)
    ax6.set_xlabel('Champions')
    ax6.set_ylabel('Speedup (2→3 threads)')
    ax6.set_title('Worst 10 Performers (Lowest Speedup)')
    ax6.set_xticks(range(len(worst_champions)))
    ax6.set_xticklabels(worst_champions, rotation=45, ha='right')
    ax6.axhline(1.0, color='black', linestyle='--', alpha=0.5)
    ax6.grid(True, alpha=0.3)
    
    # 7. Best Performers (Top 10 best speedup)
    ax7 = plt.subplot(3, 3, 7)
    best_indices = np.argsort(speedup)[-10:]
    best_champions = champions[best_indices]
    best_speedups = speedup[best_indices]
    
    bars = ax7.bar(range(len(best_champions)), best_speedups, 
                   color='green', alpha=0.7)
    ax7.set_xlabel('Champions')
    ax7.set_ylabel('Speedup (2→3 threads)')
    ax7.set_title('Best 10 Performers (Highest Speedup)')
    ax7.set_xticks(range(len(best_champions)))
    ax7.set_xticklabels(best_champions, rotation=45, ha='right')
    ax7.axhline(1.0, color='black', linestyle='--', alpha=0.5)
    ax7.grid(True, alpha=0.3)
    
    # 8. Performance by skin count ranges
    ax8 = plt.subplot(3, 3, 8)
    
    # Define skin count ranges
    ranges = [(0, 5), (5, 10), (10, 15), (15, 20), (20, float('inf'))]
    range_labels = ['1-5', '6-10', '11-15', '16-20', '20+']
    range_speedups = []
    range_counts = []
    
    for low, high in ranges:
        if high == float('inf'):
            mask = skin_counts >= low
        else:
            mask = (skin_counts >= low) & (skin_counts < high)
        
        if np.any(mask):
            range_speedups.append(np.mean(speedup[mask]))
            range_counts.append(np.sum(mask))
        else:
            range_speedups.append(0)
            range_counts.append(0)
    
    bars = ax8.bar(range_labels, range_speedups, alpha=0.7, color='purple')
    ax8.axhline(1.0, color='red', linestyle='--', alpha=0.5, label='No improvement')
    ax8.set_xlabel('Number of Skins')
    ax8.set_ylabel('Average Speedup (2→3 threads)')
    ax8.set_title('Speedup by Skin Count Range')
    ax8.legend()
    ax8.grid(True, alpha=0.3)
    
    # Add count labels on bars
    for i, (bar, count) in enumerate(zip(bars, range_counts)):
        if count > 0:
            ax8.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'n={count}', ha='center', va='bottom', fontsize=9)
    
    # 9. Summary Statistics
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis('off')
    
    # Calculate statistics
    improved_count = np.sum(speedup > 1.0)
    degraded_count = np.sum(speedup < 1.0)
    improved_performance = np.sum(degradation < 0)
    degraded_performance = np.sum(degradation > 0)
    
    worst_idx = np.argmin(speedup)
    best_idx = np.argmax(speedup)
    
    stats_text = f"""
    SUMMARY STATISTICS
    
    Total Champions Tested: {len(champions)}
    
    SPEEDUP (2→3 threads):
    • Average: {np.mean(speedup):.2f}x
    • Median: {np.median(speedup):.2f}x
    • Best: {np.max(speedup):.2f}x ({champions[best_idx]})
    • Worst: {np.min(speedup):.2f}x ({champions[worst_idx]})
    
    PERFORMANCE DEGRADATION:
    • Average: {np.mean(degradation):.1f}%
    • Median: {np.median(degradation):.1f}%
    • Champions improved: {improved_performance}
    • Champions degraded: {degraded_performance}
    
    OVERALL RESULTS:
    • Champions faster with 3 threads: {improved_count}
    • Champions slower with 3 threads: {degraded_count}
    • Success rate: {improved_count/len(champions)*100:.1f}%
    """
    
    ax9.text(0.05, 0.95, stats_text, transform=ax9.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig('thread_comparison_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    """Main function"""
    csv_file = "champion_thread_comparison.csv"
    
    try:
        print("Loading data...")
        champions, skin_counts, time_2, time_3, avg_skin_2, avg_skin_3, speedup, degradation = load_data(csv_file)
        
        print(f"Loaded data for {len(champions)} champions")
        print("\nCreating plots...")
        create_plots(champions, skin_counts, time_2, time_3, avg_skin_2, avg_skin_3, speedup, degradation)
        
        print("Plot saved as: thread_comparison_analysis.png")
        
        # Print summary
        print(f"\n=== SUMMARY ===")
        print(f"Total champions tested: {len(champions)}")
        print(f"Average speedup (2→3 threads): {np.mean(speedup):.2f}x")
        print(f"Champions that improved: {np.sum(np.array(speedup) > 1.0)}")
        print(f"Champions that got worse: {np.sum(np.array(speedup) < 1.0)}")
        print(f"Average performance degradation: {np.mean(degradation):.1f}%")
        
        # Show worst and best performers
        worst_idx = np.argmin(speedup)
        best_idx = np.argmax(speedup)
        
        print(f"\nWorst performer: {champions[worst_idx]} ({speedup[worst_idx]:.2f}x speedup)")
        print(f"Best performer: {champions[best_idx]} ({speedup[best_idx]:.2f}x speedup)")
        
    except FileNotFoundError:
        print(f"Error: {csv_file} not found!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
