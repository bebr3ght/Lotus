#!/usr/bin/env python3
"""
Test program to inject all skins for any champion in parallel
"""

import sys
import time
import threading
from pathlib import Path
from typing import List, Tuple, Dict
import csv
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from injection.manager import InjectionManager
from utils.paths import get_skins_dir
from utils.logging import setup_logging, get_logger

# Setup logging (reduce verbosity for cleaner output)
setup_logging(verbose=False)
log = get_logger()

class ChampionTimer:
    """Timer for tracking champion skin injection performance"""
    
    def __init__(self):
        self.mkoverlay_times = []
        self.skin_names = []
        self.injection_times = []
        self.successful_injections = 0
        self.failed_injections = 0
        self.lock = threading.Lock()
    
    def log_injection_result(self, skin_name: str, success: bool, mkoverlay_time: float = None, build_time: float = None):
        """Record build result with thread safety"""
        with self.lock:
            if success:
                self.successful_injections += 1
                if mkoverlay_time is not None:
                    self.mkoverlay_times.append(mkoverlay_time)
                    self.skin_names.append(skin_name)
                if build_time is not None:
                    self.injection_times.append(build_time)
            else:
                self.failed_injections += 1

def find_champion_skins(base_dir: Path, champion_name: str) -> List[Tuple[str, Path]]:
    """Find all skins for a specific champion"""
    champion_skins = []
    
    # Try different possible champion directory names
    possible_names = [champion_name, champion_name.lower(), champion_name.upper(), champion_name.capitalize()]
    
    for name in possible_names:
        champion_dir = base_dir / name
        if champion_dir.is_dir():
            for skin_zip in champion_dir.glob("*.zip"):
                champion_skins.append((skin_zip.stem, skin_zip))
            break
    
    # If no specific champion directory found, search for champion skins in all directories
    if not champion_skins:
        print(f"No {champion_name} directory found, searching all directories for {champion_name} skins...")
        champion_lower = champion_name.lower()
        for champion_dir in base_dir.iterdir():
            if champion_dir.is_dir():
                for skin_zip in champion_dir.glob(f"*{champion_lower}*.zip"):
                    champion_skins.append((skin_zip.stem, skin_zip))
                for skin_zip in champion_dir.glob(f"*{champion_name}*.zip"):
                    champion_skins.append((skin_zip.stem, skin_zip))
    
    return champion_skins

def get_mkoverlay_timing(injection_manager) -> float:
    """Retrieve the last mkoverlay timing from the injector"""
    if injection_manager.injector and injection_manager.injector.last_injection_timing:
        return injection_manager.injector.last_injection_timing.get('mkoverlay_duration')
    return None

def test_mkoverlay_build_time(skin_name: str, skin_path: Path, timer: ChampionTimer, thread_id: int) -> Dict:
    """Test mkoverlay build time for a single skin without full injection"""
    result = {
        'skin_name': skin_name,
        'skin_path': str(skin_path),
        'success': False,
        'mkoverlay_time': None,
        'build_time': None,
        'error': None
    }
    
    # Initialize variables for cleanup
    thread_base_dir = None
    build_start = None
    
    try:
        # Create thread-specific directories to avoid conflicts
        from utils.paths import get_injection_dir
        injection_base = get_injection_dir()
        thread_base_dir = injection_base / f"thread_{thread_id}"
        thread_mods_dir = thread_base_dir / "mods"
        thread_overlay_dir = thread_base_dir / "overlay"
        
        # Create thread-specific injection manager with isolated directories
        manager = InjectionManager(
            mods_dir=thread_mods_dir,
            zips_dir=get_skins_dir()
        )
        
        # Force immediate initialization instead of async
        manager._ensure_initialized()
        
        if not manager._initialized:
            result['error'] = "Failed to initialize injection manager"
            return result
        
        # Test only the mkoverlay build time
        build_start = time.time()
        success = manager.inject_skin_for_testing(skin_name)  # This only runs mkoverlay, not full injection
        build_time = time.time() - build_start
        
        result['success'] = success
        result['build_time'] = build_time
        
        if success:
            mkoverlay_time = get_mkoverlay_timing(manager)
            result['mkoverlay_time'] = mkoverlay_time
            print(f"[SUCCESS] {skin_name:40s} | build: {build_time:.3f}s | mkoverlay: {mkoverlay_time:.3f}s" if mkoverlay_time else f"[SUCCESS] {skin_name:40s} | build: {build_time:.3f}s")
            # Log result to shared timer
            timer.log_injection_result(skin_name, success, mkoverlay_time, build_time)
        else:
            print(f"[FAILED]  {skin_name:40s} | build: {build_time:.3f}s")
            # Log result to shared timer
            timer.log_injection_result(skin_name, success, None, build_time)
        
    except Exception as e:
        result['error'] = str(e)
        result['build_time'] = time.time() - build_start if build_start is not None else 0
        print(f"[ERROR]   {skin_name:40s} | error: {str(e)}")
        timer.log_injection_result(skin_name, False)
    
    finally:
        # ALWAYS clean up thread-specific directories, even on errors
        if thread_base_dir is not None:
            import shutil
            if thread_base_dir.exists():
                shutil.rmtree(thread_base_dir, ignore_errors=True)
    
    return result

def run_champion_sequential_test(champion_name: str):
    """Run the champion skins sequentially to measure actual sequential time"""
    print("=" * 80)
    print(f"{champion_name.upper()} SKINS SEQUENTIAL MKOVERLAY BUILD TEST")
    print("=" * 80)
    
    # Clean up any existing thread directories from previous runs
    from utils.paths import get_injection_dir
    import shutil
    injection_base = get_injection_dir()
    for thread_dir in injection_base.glob("thread_*"):
        if thread_dir.is_dir():
            shutil.rmtree(thread_dir, ignore_errors=True)
    
    # Get skins directory
    skins_dir = get_skins_dir()
    actual_skins_dir = skins_dir / "skins"
    print(f"Scanning {champion_name} skins directory: {actual_skins_dir}")
    
    # Find all champion skins
    champion_skins = find_champion_skins(actual_skins_dir, champion_name)
    if not champion_skins:
        print(f"ERROR: No {champion_name} skins found")
        return 0
    
    print(f"[OK] Found {len(champion_skins)} {champion_name} skins")
    
    # Sort skins by name for consistent testing order
    champion_skins.sort(key=lambda x: x[0])
    
    print("\n" + "=" * 80)
    print(f"STARTING SEQUENTIAL {champion_name.upper()} SKINS MKOVERLAY BUILD TESTS")
    print("=" * 80)
    
    # Measure actual sequential time
    sequential_start = time.time()
    
    for i, (skin_name, skin_path) in enumerate(champion_skins):
        print(f"[{i+1:2d}/{len(champion_skins)}] Processing: {skin_name}")
        
        # Create single injection manager
        manager = InjectionManager(
            mods_dir=get_injection_dir() / "mods",
            zips_dir=get_skins_dir()
        )
        
        # Force immediate initialization
        manager._ensure_initialized()
        
        if manager._initialized:
            success = manager.inject_skin_for_testing(skin_name)
            if success:
                mkoverlay_time = get_mkoverlay_timing(manager)
                print(f"[SUCCESS] {skin_name:40s} | mkoverlay: {mkoverlay_time:.3f}s" if mkoverlay_time else f"[SUCCESS] {skin_name:40s}")
            else:
                print(f"[FAILED]  {skin_name:40s}")
        
        # Clean up after each skin
        import shutil
        mods_dir = get_injection_dir() / "mods"
        overlay_dir = get_injection_dir() / "overlay"
        if mods_dir.exists():
            shutil.rmtree(mods_dir, ignore_errors=True)
        if overlay_dir.exists():
            shutil.rmtree(overlay_dir, ignore_errors=True)
    
    sequential_time = time.time() - sequential_start
    print(f"\n[SEQUENTIAL] Total time: {sequential_time:.2f}s")
    
    # Save sequential time to file for comparison
    seq_time_file = Path(f"{champion_name.lower()}_sequential_time.txt")
    with open(seq_time_file, 'w') as f:
        f.write(f"{sequential_time:.3f}")
    print(f"[SAVED] Sequential time saved to: {seq_time_file}")
    
    return sequential_time

def get_sequential_time(champion_name: str):
    """Get the stored sequential time if available"""
    seq_time_file = Path(f"{champion_name.lower()}_sequential_time.txt")
    if seq_time_file.exists():
        try:
            with open(seq_time_file, 'r') as f:
                return float(f.read().strip())
        except:
            return None
    return None

def run_champion_parallel_test(champion_name: str, max_workers: int = None):
    """Run the champion skins parallel mkoverlay build test"""
    print("=" * 80)
    print(f"{champion_name.upper()} SKINS PARALLEL MKOVERLAY BUILD TEST")
    print("=" * 80)
    
    # Clean up any existing thread directories from previous runs
    from utils.paths import get_injection_dir
    import shutil
    injection_base = get_injection_dir()
    for thread_dir in injection_base.glob("thread_*"):
        if thread_dir.is_dir():
            shutil.rmtree(thread_dir, ignore_errors=True)
            print(f"[CLEANUP] Removed leftover thread directory: {thread_dir}")
    
    # Initialize shared timer
    timer = ChampionTimer()
    
    # Get skins directory
    skins_dir = get_skins_dir()
    actual_skins_dir = skins_dir / "skins"
    print(f"Scanning {champion_name} skins directory: {actual_skins_dir}")
    
    # Find all champion skins
    champion_skins = find_champion_skins(actual_skins_dir, champion_name)
    if not champion_skins:
        print(f"ERROR: No {champion_name} skins found")
        return
    
    print(f"[OK] Found {len(champion_skins)} {champion_name} skins")
    
    # Sort skins by name for consistent testing order
    champion_skins.sort(key=lambda x: x[0])
    
    # Set max_workers to a reasonable default to avoid system overload
    if max_workers is None:
        # Use minimum of 4 workers or number of skins, whichever is smaller
        # This prevents system overload while still getting good parallelization
        max_workers = min(4, len(champion_skins))
    
    print(f"\nUsing {max_workers} parallel workers (one per skin)")
    print("\n" + "=" * 80)
    print(f"STARTING PARALLEL {champion_name.upper()} SKINS MKOVERLAY BUILD TESTS")
    print("=" * 80)
    
    # Store all results
    all_results = []
    start_time = time.time()
    
    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all mkoverlay build tasks with unique thread IDs
        future_to_skin = {
            executor.submit(test_mkoverlay_build_time, skin_name, skin_path, timer, i): (skin_name, skin_path)
            for i, (skin_name, skin_path) in enumerate(champion_skins)
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_skin):
            skin_name, skin_path = future_to_skin[future]
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                print(f"[ERROR] Exception for {skin_name}: {e}")
                all_results.append({
                    'skin_name': skin_name,
                    'skin_path': str(skin_path),
                    'success': False,
                    'mkoverlay_time': None,
                    'build_time': None,
                    'error': str(e)
                })
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"{champion_name.upper()} PARALLEL MKOVERLAY BUILD TEST RESULTS")
    print("=" * 80)
    print(f"Total test time: {total_time:.2f}s")
    print(f"Successful builds: {timer.successful_injections}")
    print(f"Failed builds: {timer.failed_injections}")
    print(f"Total {champion_name} skins tested: {len(champion_skins)}")
    print(f"Parallel workers used: {max_workers}")
    
    if timer.mkoverlay_times:
        times_list = timer.mkoverlay_times
        
        # Calculate statistics
        mean_time = statistics.mean(times_list)
        median_time = statistics.median(times_list)
        std_time = statistics.stdev(times_list) if len(times_list) > 1 else 0
        min_time = min(times_list)
        max_time = max(times_list)
        
        print(f"\n{champion_name} Skins mkoverlay Timing Statistics:")
        print(f"  Mean: {mean_time:.3f}s")
        print(f"  Median: {median_time:.3f}s")
        print(f"  Std Dev: {std_time:.3f}s")
        print(f"  Min: {min_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")
        
        # Rank skins by speed
        ranked_skins = sorted(zip(timer.skin_names, timer.mkoverlay_times), key=lambda x: x[1])
        print(f"\n{champion_name} Skins Ranked by Speed (fastest to slowest):")
        print("-" * 70)
        for i, (skin, time_val) in enumerate(ranked_skins):
            print(f"{i+1:2d}. {skin:40s} | {time_val:.3f}s")
        
        # Create text-based histogram
        print(f"\nText-based Histogram ({champion_name} mkoverlay timing):")
        histogram = {}
        bin_size = 0.1  # 0.1 second bins
        for time_val in times_list:
            bin_val = round(time_val / bin_size) * bin_size
            histogram[bin_val] = histogram.get(bin_val, 0) + 1
        
        for bin_val in sorted(histogram.keys()):
            count = histogram[bin_val]
            bar = "*" * (count * 50 // len(times_list))  # Scale to max 50 chars
            print(f"  {bin_val:4.1f}s: {count:2d} {bar}")
        
        # Save raw data
        data_path = Path(f"{champion_name.lower()}_parallel_mkoverlay_timing.csv")
        with open(data_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Skin", "mkoverlay_time", "build_time", "success"])
            for result in all_results:
                if result['mkoverlay_time'] is not None:
                    writer.writerow([
                        result['skin_name'], 
                        f"{result['mkoverlay_time']:.3f}",
                        f"{result['build_time']:.3f}",
                        result['success']
                    ])
        print(f"[OK] {champion_name} mkoverlay timing data saved to: {data_path}")
    
    # Performance summary - just the real times
    print(f"\nReal Test Times:")
    print(f"  Parallel test time: {total_time:.2f}s")
    
    # Check if we have sequential time for comparison
    sequential_time = get_sequential_time(champion_name)
    if sequential_time:
        print(f"  Sequential test time: {sequential_time:.2f}s")
        print(f"  Speedup: {sequential_time / total_time:.2f}x")
    else:
        print(f"  (Run 'python test_champion_skins.py {champion_name} --sequential' to get sequential time)")
    
    # Error summary
    failed_skins = [r for r in all_results if not r['success']]
    if failed_skins:
        print(f"\nFailed Builds Summary:")
        print("-" * 50)
        for result in failed_skins:
            error_msg = result.get('error', 'Unknown error')
            print(f"  {result['skin_name']:40s} | {error_msg}")
    else:
        print(f"\n[SUCCESS] All {len(champion_skins)} {champion_name} skins mkoverlay builds completed successfully!")

def run_all_champions_comparison():
    """Run 2 vs 3 thread comparison for all champions"""
    print("=" * 80)
    print("ALL CHAMPIONS 2 vs 3 THREAD COMPARISON")
    print("=" * 80)
    
    # Get all available champions
    skins_dir = get_skins_dir() / "skins"
    champions = []
    for champion_dir in skins_dir.iterdir():
        if champion_dir.is_dir() and champion_dir.name not in [".", ".."]:
            # Check if it has skin files
            skin_files = list(champion_dir.glob("*.zip"))
            if skin_files:
                champions.append(champion_dir.name)
    
    champions.sort()
    print(f"Found {len(champions)} champions with skins")
    
    # Prepare CSV output
    csv_file = Path("champion_thread_comparison.csv")
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Champion", "Skin_Count", 
            "2_Threads_Total_Time", "2_Threads_Avg_Skin_Time", "2_Threads_Efficiency",
            "3_Threads_Total_Time", "3_Threads_Avg_Skin_Time", "3_Threads_Efficiency",
            "Speedup_2_to_3", "Efficiency_Change", "Performance_Degradation"
        ])
    
    print("\nStarting comparison tests...")
    print("=" * 80)
    
    for i, champion in enumerate(champions, 1):
        print(f"\n[{i:2d}/{len(champions)}] Testing {champion}...")
        
        try:
            # Test with 2 threads
            print(f"  Running {champion} with 2 threads...")
            result_2 = run_champion_parallel_test_silent(champion, 2)
            
            # Test with 3 threads  
            print(f"  Running {champion} with 3 threads...")
            result_3 = run_champion_parallel_test_silent(champion, 3)
            
            # Calculate metrics
            skin_count = result_2['skin_count']
            
            # 2 thread metrics
            time_2 = result_2['total_time']
            avg_skin_2 = result_2['avg_skin_time']
            efficiency_2 = (result_2['sequential_estimate'] / time_2) * 100 if result_2['sequential_estimate'] else 0
            
            # 3 thread metrics
            time_3 = result_3['total_time']
            avg_skin_3 = result_3['avg_skin_time']
            efficiency_3 = (result_3['sequential_estimate'] / time_3) * 100 if result_3['sequential_estimate'] else 0
            
            # Comparison metrics
            speedup = time_2 / time_3 if time_3 > 0 else 0
            efficiency_change = efficiency_3 - efficiency_2
            degradation = (avg_skin_3 - avg_skin_2) / avg_skin_2 * 100 if avg_skin_2 > 0 else 0
            
            # Write to CSV
            with open(csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    champion, skin_count,
                    f"{time_2:.2f}", f"{avg_skin_2:.3f}", f"{efficiency_2:.1f}%",
                    f"{time_3:.2f}", f"{avg_skin_3:.3f}", f"{efficiency_3:.1f}%",
                    f"{speedup:.2f}x", f"{efficiency_change:+.1f}%", f"{degradation:+.1f}%"
                ])
            
            # Print summary
            print(f"  Results: 2t={time_2:.1f}s, 3t={time_3:.1f}s, speedup={speedup:.2f}x, degradation={degradation:+.1f}%")
            
        except Exception as e:
            print(f"  ERROR testing {champion}: {e}")
            # Write error row
            with open(csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([champion, "ERROR", str(e)] + [""] * 9)
    
    print(f"\n" + "=" * 80)
    print(f"COMPARISON COMPLETE - Results saved to: {csv_file}")
    print("=" * 80)

def run_champion_parallel_test_silent(champion_name: str, max_workers: int):
    """Silent version of parallel test that returns metrics instead of printing"""
    # Clean up any existing thread directories
    from utils.paths import get_injection_dir
    import shutil
    injection_base = get_injection_dir()
    for thread_dir in injection_base.glob("thread_*"):
        if thread_dir.is_dir():
            shutil.rmtree(thread_dir, ignore_errors=True)
    
    # Initialize timer
    timer = ChampionTimer()
    
    # Get skins
    skins_dir = get_skins_dir()
    actual_skins_dir = skins_dir / "skins"
    champion_skins = find_champion_skins(actual_skins_dir, champion_name)
    
    if not champion_skins:
        return {'error': f'No {champion_name} skins found'}
    
    champion_skins.sort(key=lambda x: x[0])
    
    # Run test
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_skin = {
            executor.submit(test_mkoverlay_build_time, skin_name, skin_path, timer, i): (skin_name, skin_path)
            for i, (skin_name, skin_path) in enumerate(champion_skins)
        }
        
        all_results = []
        for future in as_completed(future_to_skin):
            skin_name, skin_path = future_to_skin[future]
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                all_results.append({
                    'skin_name': skin_name,
                    'skin_path': str(skin_path),
                    'success': False,
                    'mkoverlay_time': None,
                    'build_time': None,
                    'error': str(e)
                })
    
    total_time = time.time() - start_time
    
    # Calculate metrics
    successful_builds = len([r for r in all_results if r['success']])
    avg_skin_time = statistics.mean([r['mkoverlay_time'] for r in all_results if r['mkoverlay_time']]) if successful_builds > 0 else 0
    
    # Estimate sequential time (average skin time * number of skins)
    sequential_estimate = avg_skin_time * len(champion_skins) if avg_skin_time > 0 else 0
    
    return {
        'skin_count': len(champion_skins),
        'successful_builds': successful_builds,
        'total_time': total_time,
        'avg_skin_time': avg_skin_time,
        'sequential_estimate': sequential_estimate,
        'mkoverlay_times': timer.mkoverlay_times
    }

if __name__ == "__main__":
    # Handle command line arguments
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_champion_skins.py <champion_name>                    # Run parallel with 4 workers")
        print("  python test_champion_skins.py <champion_name> N                  # Run parallel with N workers")
        print("  python test_champion_skins.py <champion_name> --sequential       # Run sequential test")
        print("  python test_champion_skins.py --compare-all                       # Compare 2 vs 3 threads for all champions")
        print("\nExample:")
        print("  python test_champion_skins.py Anivia")
        print("  python test_champion_skins.py Lux 6")
        print("  python test_champion_skins.py Ahri --sequential")
        print("  python test_champion_skins.py --compare-all")
        sys.exit(1)
    
    if sys.argv[1] == "--compare-all":
        run_all_champions_comparison()
    else:
        champion_name = sys.argv[1]
        
        if len(sys.argv) > 2:
            if sys.argv[2] == "--sequential":
                print(f"Running sequential test for {champion_name} to measure actual sequential time...")
                sequential_time = run_champion_sequential_test(champion_name)
                print(f"\nSequential time measured: {sequential_time:.2f}s")
                print("Use this time to compare with parallel results.")
            else:
                try:
                    max_workers = int(sys.argv[2])
                    print(f"Using {max_workers} parallel workers for {champion_name} (from command line argument)")
                    run_champion_parallel_test(champion_name, max_workers)
                except ValueError:
                    print(f"Invalid argument '{sys.argv[2]}'")
                    print("Usage:")
                    print(f"  python test_champion_skins.py {champion_name}                    # Run parallel with 4 workers")
                    print(f"  python test_champion_skins.py {champion_name} N                  # Run parallel with N workers")
                    print(f"  python test_champion_skins.py {champion_name} --sequential       # Run sequential test")
        else:
            print(f"Using default of 4 parallel workers for {champion_name} (use command line argument to override)")
            run_champion_parallel_test(champion_name)
