#!/usr/bin/env python3
"""
Simple text-based analysis of thread comparison results
"""

import csv
import statistics

def load_data(csv_file):
    """Load data from CSV file"""
    data = []
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Skin_Count'] != 'ERROR':
                # Clean up the speedup value (remove 'x' suffix)
                speedup_str = row['Speedup_2_to_3'].rstrip('x')
                
                # Clean up the degradation value (remove '%' suffix and '+' prefix)
                degradation_str = row['Performance_Degradation'].rstrip('%').lstrip('+')
                
                data.append({
                    'champion': row['Champion'],
                    'skin_count': int(row['Skin_Count']),
                    'time_2': float(row['2_Threads_Total_Time']),
                    'time_3': float(row['3_Threads_Total_Time']),
                    'avg_skin_2': float(row['2_Threads_Avg_Skin_Time']),
                    'avg_skin_3': float(row['3_Threads_Avg_Skin_Time']),
                    'speedup': float(speedup_str),
                    'degradation': float(degradation_str)
                })
    
    return data

def analyze_data(data):
    """Analyze the data and print results"""
    
    if not data:
        print("No data to analyze!")
        return
    
    print("=" * 80)
    print("THREAD COMPARISON ANALYSIS (2 vs 3 threads)")
    print("=" * 80)
    
    # Basic statistics
    speedups = [d['speedup'] for d in data]
    degradations = [d['degradation'] for d in data]
    skin_counts = [d['skin_count'] for d in data]
    
    print(f"\nBASIC STATISTICS:")
    print(f"Total champions tested: {len(data)}")
    print(f"Average speedup (2->3 threads): {statistics.mean(speedups):.2f}x")
    print(f"Median speedup: {statistics.median(speedups):.2f}x")
    print(f"Standard deviation: {statistics.stdev(speedups):.2f}")
    print(f"Min speedup: {min(speedups):.2f}x")
    print(f"Max speedup: {max(speedups):.2f}x")
    
    print(f"\nPERFORMANCE DEGRADATION:")
    print(f"Average degradation: {statistics.mean(degradations):.1f}%")
    print(f"Median degradation: {statistics.median(degradations):.1f}%")
    print(f"Standard deviation: {statistics.stdev(degradations):.1f}%")
    
    # Success analysis
    improved = [d for d in data if d['speedup'] > 1.0]
    degraded = [d for d in data if d['speedup'] < 1.0]
    same = [d for d in data if d['speedup'] == 1.0]
    
    print(f"\nSUCCESS ANALYSIS:")
    print(f"Champions that improved: {len(improved)} ({len(improved)/len(data)*100:.1f}%)")
    print(f"Champions that got worse: {len(degraded)} ({len(degraded)/len(data)*100:.1f}%)")
    print(f"Champions with no change: {len(same)} ({len(same)/len(data)*100:.1f}%)")
    
    # Performance improvement analysis
    improved_perf = [d for d in data if d['degradation'] < 0]
    degraded_perf = [d for d in data if d['degradation'] > 0]
    
    print(f"\nINDIVIDUAL SKIN PERFORMANCE:")
    print(f"Champions with improved individual skin times: {len(improved_perf)} ({len(improved_perf)/len(data)*100:.1f}%)")
    print(f"Champions with degraded individual skin times: {len(degraded_perf)} ({len(degraded_perf)/len(data)*100:.1f}%)")
    
    # Best and worst performers
    best = max(data, key=lambda x: x['speedup'])
    worst = min(data, key=lambda x: x['speedup'])
    
    print(f"\nBEST PERFORMER:")
    print(f"  {best['champion']}: {best['speedup']:.2f}x speedup")
    print(f"  Skins: {best['skin_count']}, 2t: {best['time_2']:.1f}s, 3t: {best['time_3']:.1f}s")
    print(f"  Individual skin degradation: {best['degradation']:+.1f}%")
    
    print(f"\nWORST PERFORMER:")
    print(f"  {worst['champion']}: {worst['speedup']:.2f}x speedup")
    print(f"  Skins: {worst['skin_count']}, 2t: {worst['time_2']:.1f}s, 3t: {worst['time_3']:.1f}s")
    print(f"  Individual skin degradation: {worst['degradation']:+.1f}%")
    
    # Analysis by skin count ranges
    print(f"\nANALYSIS BY SKIN COUNT:")
    ranges = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 999)]
    range_names = ['1-5 skins', '6-10 skins', '11-15 skins', '16-20 skins', '20+ skins']
    
    for (low, high), name in zip(ranges, range_names):
        range_data = [d for d in data if low <= d['skin_count'] <= high]
        if range_data:
            range_speedups = [d['speedup'] for d in range_data]
            range_improved = len([d for d in range_data if d['speedup'] > 1.0])
            avg_speedup = statistics.mean(range_speedups)
            print(f"  {name}: {len(range_data)} champions, avg speedup {avg_speedup:.2f}x, {range_improved}/{len(range_data)} improved")
    
    # Top 10 best and worst
    print(f"\nTOP 10 BEST PERFORMERS:")
    best_10 = sorted(data, key=lambda x: x['speedup'], reverse=True)[:10]
    for i, d in enumerate(best_10, 1):
        print(f"  {i:2d}. {d['champion']:15s} {d['speedup']:5.2f}x ({d['skin_count']} skins, {d['degradation']:+.1f}% degradation)")
    
    print(f"\nTOP 10 WORST PERFORMERS:")
    worst_10 = sorted(data, key=lambda x: x['speedup'])[:10]
    for i, d in enumerate(worst_10, 1):
        print(f"  {i:2d}. {d['champion']:15s} {d['speedup']:5.2f}x ({d['skin_count']} skins, {d['degradation']:+.1f}% degradation)")
    
    # Champions with significant degradation
    significant_degradation = [d for d in data if d['degradation'] > 50]
    if significant_degradation:
        print(f"\nCHAMPIONS WITH >50% INDIVIDUAL SKIN DEGRADATION:")
        for d in sorted(significant_degradation, key=lambda x: x['degradation'], reverse=True):
            print(f"  {d['champion']:15s} {d['degradation']:6.1f}% degradation, {d['speedup']:5.2f}x speedup")
    
    # Champions with significant improvement
    significant_improvement = [d for d in data if d['degradation'] < -20]
    if significant_improvement:
        print(f"\nCHAMPIONS WITH >20% INDIVIDUAL SKIN IMPROVEMENT:")
        for d in sorted(significant_improvement, key=lambda x: x['degradation']):
            print(f"  {d['champion']:15s} {d['degradation']:6.1f}% degradation, {d['speedup']:5.2f}x speedup")
    
    # Summary recommendations
    print(f"\nRECOMMENDATIONS:")
    
    avg_speedup = statistics.mean(speedups)
    if avg_speedup > 1.2:
        print(f"  YES 3 threads generally perform better (avg {avg_speedup:.2f}x speedup)")
    elif avg_speedup < 0.8:
        print(f"  NO 3 threads generally perform worse (avg {avg_speedup:.2f}x speedup)")
        print(f"    Recommendation: Stick with 2 threads")
    else:
        print(f"  MIXED results (avg {avg_speedup:.2f}x speedup)")
        print(f"    Recommendation: Test individual champions")
    
    high_degradation_count = len([d for d in data if d['degradation'] > 50])
    if high_degradation_count > len(data) * 0.2:  # More than 20% have high degradation
        print(f"  WARNING: {high_degradation_count} champions show >50% individual skin degradation")
        print(f"    This suggests potential resource contention issues")
    
    print(f"\n" + "=" * 80)

def main():
    """Main function"""
    csv_file = "champion_thread_comparison.csv"
    
    try:
        print("Loading data from CSV...")
        data = load_data(csv_file)
        
        if not data:
            print("No valid data found in CSV file!")
            return
        
        analyze_data(data)
        
    except FileNotFoundError:
        print(f"Error: {csv_file} not found!")
        print("Make sure you've run the thread comparison test first.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
