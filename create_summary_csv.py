#!/usr/bin/env python3
"""
Create a summary CSV with key metrics for easy reference
"""

import csv

def create_summary():
    """Create a summary CSV file"""
    
    # Read the full data
    data = []
    with open('champion_thread_comparison.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Skin_Count'] != 'ERROR':
                speedup_str = row['Speedup_2_to_3'].rstrip('x')
                degradation_str = row['Performance_Degradation'].rstrip('%').lstrip('+')
                
                data.append({
                    'Champion': row['Champion'],
                    'Skin_Count': int(row['Skin_Count']),
                    'Speedup': float(speedup_str),
                    'Performance_Degradation': float(degradation_str),
                    'Total_Time_2_Threads': float(row['2_Threads_Total_Time']),
                    'Total_Time_3_Threads': float(row['3_Threads_Total_Time']),
                    'Avg_Skin_Time_2_Threads': float(row['2_Threads_Avg_Skin_Time']),
                    'Avg_Skin_Time_3_Threads': float(row['3_Threads_Avg_Skin_Time'])
                })
    
    # Sort by speedup (best first)
    data.sort(key=lambda x: x['Speedup'], reverse=True)
    
    # Write summary CSV
    with open('thread_comparison_summary.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Champion', 'Skin_Count', 'Speedup_2_to_3', 'Performance_Degradation_%',
            'Total_Time_2_Threads_s', 'Total_Time_3_Threads_s', 'Time_Saved_s',
            'Avg_Skin_Time_2_Threads_s', 'Avg_Skin_Time_3_Threads_s', 'Recommendation'
        ])
        
        for d in data:
            time_saved = d['Total_Time_2_Threads'] - d['Total_Time_3_Threads']
            
            # Determine recommendation
            if d['Speedup'] > 1.3:
                recommendation = "STRONGLY RECOMMEND 3 threads"
            elif d['Speedup'] > 1.1:
                recommendation = "RECOMMEND 3 threads"
            elif d['Speedup'] > 0.9:
                recommendation = "MIXED - test individually"
            else:
                recommendation = "STICK WITH 2 threads"
            
            writer.writerow([
                d['Champion'],
                d['Skin_Count'],
                f"{d['Speedup']:.2f}",
                f"{d['Performance_Degradation']:+.1f}",
                f"{d['Total_Time_2_Threads']:.2f}",
                f"{d['Total_Time_3_Threads']:.2f}",
                f"{time_saved:+.2f}",
                f"{d['Avg_Skin_Time_2_Threads']:.3f}",
                f"{d['Avg_Skin_Time_3_Threads']:.3f}",
                recommendation
            ])
    
    print("Summary CSV created: thread_comparison_summary.csv")
    
    # Print quick stats
    improved = len([d for d in data if d['Speedup'] > 1.0])
    avg_speedup = sum(d['Speedup'] for d in data) / len(data)
    
    print(f"\nQuick Stats:")
    print(f"- {improved}/{len(data)} champions improved with 3 threads")
    print(f"- Average speedup: {avg_speedup:.2f}x")
    print(f"- Best performer: {data[0]['Champion']} ({data[0]['Speedup']:.2f}x)")
    print(f"- Worst performer: {data[-1]['Champion']} ({data[-1]['Speedup']:.2f}x)")

if __name__ == "__main__":
    create_summary()
