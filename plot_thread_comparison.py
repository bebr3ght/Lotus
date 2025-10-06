#!/usr/bin/env python3
"""
Plot thread comparison results from CSV file
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

def load_and_clean_data(csv_file):
    """Load and clean the CSV data"""
    df = pd.read_csv(csv_file)
    
    # Clean up percentage columns
    for col in ['2_Threads_Efficiency', '3_Threads_Efficiency', 'Efficiency_Change', 'Performance_Degradation']:
        df[col] = df[col].str.rstrip('%').astype(float)
    
    # Clean up speedup column
    df['Speedup_2_to_3'] = df['Speedup_2_to_3'].str.rstrip('x').astype(float)
    
    # Filter out error rows
    df = df[df['Skin_Count'] != 'ERROR']
    df['Skin_Count'] = pd.to_numeric(df['Skin_Count'])
    
    return df

def create_performance_plots(df):
    """Create comprehensive performance comparison plots"""
    
    # Set up the plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Create figure with subplots
    fig = plt.figure(figsize=(20, 16))
    
    # 1. Speedup Distribution
    ax1 = plt.subplot(3, 3, 1)
    speedup_data = df['Speedup_2_to_3']
    ax1.hist(speedup_data, bins=20, alpha=0.7, edgecolor='black')
    ax1.axvline(1.0, color='red', linestyle='--', linewidth=2, label='No improvement')
    ax1.set_xlabel('Speedup (2→3 threads)')
    ax1.set_ylabel('Number of Champions')
    ax1.set_title('Distribution of 2→3 Thread Speedup')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Performance Degradation Distribution
    ax2 = plt.subplot(3, 3, 2)
    degradation_data = df['Performance_Degradation']
    ax2.hist(degradation_data, bins=20, alpha=0.7, edgecolor='black', color='orange')
    ax2.axvline(0, color='red', linestyle='--', linewidth=2, label='No degradation')
    ax2.set_xlabel('Performance Degradation (%)')
    ax2.set_ylabel('Number of Champions')
    ax2.set_title('Individual Skin Time Degradation (2→3 threads)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Speedup vs Skin Count
    ax3 = plt.subplot(3, 3, 3)
    scatter = ax3.scatter(df['Skin_Count'], df['Speedup_2_to_3'], 
                         c=df['Performance_Degradation'], 
                         cmap='RdYlGn', alpha=0.7, s=60)
    ax3.axhline(1.0, color='red', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Number of Skins')
    ax3.set_ylabel('Speedup (2→3 threads)')
    ax3.set_title('Speedup vs Skin Count\n(Color = Performance Degradation)')
    plt.colorbar(scatter, ax=ax3, label='Performance Degradation (%)')
    ax3.grid(True, alpha=0.3)
    
    # 4. Efficiency Change Distribution
    ax4 = plt.subplot(3, 3, 4)
    efficiency_data = df['Efficiency_Change']
    ax4.hist(efficiency_data, bins=20, alpha=0.7, edgecolor='black', color='green')
    ax4.axvline(0, color='red', linestyle='--', linewidth=2, label='No change')
    ax4.set_xlabel('Efficiency Change (%)')
    ax4.set_ylabel('Number of Champions')
    ax4.set_title('Efficiency Change (2→3 threads)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. Average Skin Time Comparison
    ax5 = plt.subplot(3, 3, 5)
    x_pos = np.arange(len(df))
    width = 0.35
    ax5.bar(x_pos - width/2, df['2_Threads_Avg_Skin_Time'], width, 
            label='2 Threads', alpha=0.8, color='skyblue')
    ax5.bar(x_pos + width/2, df['3_Threads_Avg_Skin_Time'], width, 
            label='3 Threads', alpha=0.8, color='lightcoral')
    ax5.set_xlabel('Champions (sorted by 2-thread time)')
    ax5.set_ylabel('Average Skin Time (seconds)')
    ax5.set_title('Average Skin Time: 2 vs 3 Threads')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    ax5.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
    
    # 6. Total Time Comparison
    ax6 = plt.subplot(3, 3, 6)
    ax6.bar(x_pos - width/2, df['2_Threads_Total_Time'], width, 
            label='2 Threads', alpha=0.8, color='lightgreen')
    ax6.bar(x_pos + width/2, df['3_Threads_Total_Time'], width, 
            label='3 Threads', alpha=0.8, color='orange')
    ax6.set_xlabel('Champions (sorted by 2-thread time)')
    ax6.set_ylabel('Total Time (seconds)')
    ax6.set_title('Total Time: 2 vs 3 Threads')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    ax6.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
    
    # 7. Worst Performers (Top 10 worst speedup)
    ax7 = plt.subplot(3, 3, 7)
    worst_performers = df.nsmallest(10, 'Speedup_2_to_3')
    bars = ax7.bar(range(len(worst_performers)), worst_performers['Speedup_2_to_3'], 
                   color='red', alpha=0.7)
    ax7.set_xlabel('Champions')
    ax7.set_ylabel('Speedup (2→3 threads)')
    ax7.set_title('Worst 10 Performers (Lowest Speedup)')
    ax7.set_xticks(range(len(worst_performers)))
    ax7.set_xticklabels(worst_performers['Champion'], rotation=45, ha='right')
    ax7.axhline(1.0, color='black', linestyle='--', alpha=0.5)
    ax7.grid(True, alpha=0.3)
    
    # 8. Best Performers (Top 10 best speedup)
    ax8 = plt.subplot(3, 3, 8)
    best_performers = df.nlargest(10, 'Speedup_2_to_3')
    bars = ax8.bar(range(len(best_performers)), best_performers['Speedup_2_to_3'], 
                   color='green', alpha=0.7)
    ax8.set_xlabel('Champions')
    ax8.set_ylabel('Speedup (2→3 threads)')
    ax8.set_title('Best 10 Performers (Highest Speedup)')
    ax8.set_xticks(range(len(best_performers)))
    ax8.set_xticklabels(best_performers['Champion'], rotation=45, ha='right')
    ax8.axhline(1.0, color='black', linestyle='--', alpha=0.5)
    ax8.grid(True, alpha=0.3)
    
    # 9. Summary Statistics
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis('off')
    
    # Calculate summary statistics
    stats_text = f"""
    SUMMARY STATISTICS
    
    Total Champions Tested: {len(df)}
    
    SPEEDUP (2→3 threads):
    • Average: {df['Speedup_2_to_3'].mean():.2f}x
    • Median: {df['Speedup_2_to_3'].median():.2f}x
    • Best: {df['Speedup_2_to_3'].max():.2f}x ({df.loc[df['Speedup_2_to_3'].idxmax(), 'Champion']})
    • Worst: {df['Speedup_2_to_3'].min():.2f}x ({df.loc[df['Speedup_2_to_3'].idxmin(), 'Champion']})
    
    PERFORMANCE DEGRADATION:
    • Average: {df['Performance_Degradation'].mean():.1f}%
    • Median: {df['Performance_Degradation'].median():.1f}%
    • Champions improved: {(df['Performance_Degradation'] < 0).sum()}
    • Champions degraded: {(df['Performance_Degradation'] > 0).sum()}
    
    EFFICIENCY:
    • Avg 2-thread efficiency: {df['2_Threads_Efficiency'].mean():.1f}%
    • Avg 3-thread efficiency: {df['3_Threads_Efficiency'].mean():.1f}%
    • Avg efficiency change: {df['Efficiency_Change'].mean():.1f}%
    """
    
    ax9.text(0.05, 0.95, stats_text, transform=ax9.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig('thread_comparison_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_detailed_analysis(df):
    """Create detailed analysis plots"""
    
    # Filter champions with significant differences
    significant_diff = df[abs(df['Performance_Degradation']) > 10]
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Champions with significant performance differences
    ax1 = axes[0, 0]
    if len(significant_diff) > 0:
        significant_diff_sorted = significant_diff.sort_values('Performance_Degradation')
        colors = ['red' if x > 0 else 'green' for x in significant_diff_sorted['Performance_Degradation']]
        bars = ax1.barh(range(len(significant_diff_sorted)), 
                       significant_diff_sorted['Performance_Degradation'],
                       color=colors, alpha=0.7)
        ax1.set_yticks(range(len(significant_diff_sorted)))
        ax1.set_yticklabels(significant_diff_sorted['Champion'])
        ax1.axvline(0, color='black', linestyle='-', alpha=0.5)
        ax1.set_xlabel('Performance Degradation (%)')
        ax1.set_title(f'Champions with >10% Performance Change\n({len(significant_diff)} champions)')
        ax1.grid(True, alpha=0.3)
    
    # 2. Speedup vs Performance Degradation scatter
    ax2 = axes[0, 1]
    scatter = ax2.scatter(df['Performance_Degradation'], df['Speedup_2_to_3'], 
                         c=df['Skin_Count'], cmap='viridis', alpha=0.7, s=60)
    ax2.axhline(1.0, color='red', linestyle='--', alpha=0.5, label='No improvement')
    ax2.axvline(0, color='red', linestyle='--', alpha=0.5, label='No degradation')
    ax2.set_xlabel('Performance Degradation (%)')
    ax2.set_ylabel('Speedup (2→3 threads)')
    ax2.set_title('Speedup vs Performance Degradation\n(Color = Skin Count)')
    plt.colorbar(scatter, ax=ax2, label='Number of Skins')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Efficiency comparison
    ax3 = axes[1, 0]
    x_pos = np.arange(len(df))
    ax3.scatter(df['2_Threads_Efficiency'], df['3_Threads_Efficiency'], 
               alpha=0.7, s=60, c=df['Skin_Count'], cmap='plasma')
    
    # Add diagonal line (no change)
    min_eff = min(df['2_Threads_Efficiency'].min(), df['3_Threads_Efficiency'].min())
    max_eff = max(df['2_Threads_Efficiency'].max(), df['3_Threads_Efficiency'].max())
    ax3.plot([min_eff, max_eff], [min_eff, max_eff], 'r--', alpha=0.5, label='No change')
    
    ax3.set_xlabel('2-Thread Efficiency (%)')
    ax3.set_ylabel('3-Thread Efficiency (%)')
    ax3.set_title('Efficiency Comparison: 2 vs 3 Threads\n(Color = Skin Count)')
    plt.colorbar(scatter, ax=ax3, label='Number of Skins')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. Performance by skin count ranges
    ax4 = axes[1, 1]
    
    # Create skin count bins
    df['Skin_Range'] = pd.cut(df['Skin_Count'], 
                             bins=[0, 5, 10, 15, 20, float('inf')], 
                             labels=['1-5', '6-10', '11-15', '16-20', '20+'])
    
    skin_stats = df.groupby('Skin_Range').agg({
        'Speedup_2_to_3': ['mean', 'std', 'count'],
        'Performance_Degradation': ['mean', 'std']
    }).round(2)
    
    # Flatten column names
    skin_stats.columns = ['_'.join(col).strip() for col in skin_stats.columns]
    
    # Plot speedup by skin range
    skin_ranges = skin_stats.index
    speedup_means = skin_stats['Speedup_2_to_3_mean']
    speedup_stds = skin_stats['Speedup_2_to_3_std']
    
    bars = ax4.bar(skin_ranges, speedup_means, yerr=speedup_stds, 
                   capsize=5, alpha=0.7, color='skyblue')
    ax4.axhline(1.0, color='red', linestyle='--', alpha=0.5, label='No improvement')
    ax4.set_xlabel('Number of Skins')
    ax4.set_ylabel('Average Speedup (2→3 threads)')
    ax4.set_title('Speedup by Skin Count Range')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # Add count labels on bars
    for i, (bar, count) in enumerate(zip(bars, skin_stats['Speedup_2_to_3_count'])):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'n={int(count)}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('detailed_thread_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    """Main function to create all plots"""
    csv_file = Path("champion_thread_comparison.csv")
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found!")
        return
    
    print("Loading data...")
    df = load_and_clean_data(csv_file)
    
    print(f"Loaded data for {len(df)} champions")
    print("\nCreating performance comparison plots...")
    create_performance_plots(df)
    
    print("Creating detailed analysis plots...")
    create_detailed_analysis(df)
    
    print("\nPlots saved as:")
    print("- thread_comparison_analysis.png")
    print("- detailed_thread_analysis.png")
    
    # Print summary to console
    print(f"\n=== SUMMARY ===")
    print(f"Total champions tested: {len(df)}")
    print(f"Average speedup (2→3 threads): {df['Speedup_2_to_3'].mean():.2f}x")
    print(f"Champions that improved: {(df['Speedup_2_to_3'] > 1.0).sum()}")
    print(f"Champions that got worse: {(df['Speedup_2_to_3'] < 1.0).sum()}")
    print(f"Average performance degradation: {df['Performance_Degradation'].mean():.1f}%")
    
    # Show worst and best performers
    worst = df.loc[df['Speedup_2_to_3'].idxmin()]
    best = df.loc[df['Speedup_2_to_3'].idxmax()]
    
    print(f"\nWorst performer: {worst['Champion']} ({worst['Speedup_2_to_3']:.2f}x speedup)")
    print(f"Best performer: {best['Champion']} ({best['Speedup_2_to_3']:.2f}x speedup)")

if __name__ == "__main__":
    main()
