# Testing Late Injection System

## 🎯 Objective

Determine if late injection (when prebuild isn't ready) works reliably due to natural CPU contention between injection and game opening.

---

## 📋 Testing Phases

### **Phase 1: Natural Late Injection (Current System)**

**Configuration:**

```python
# constants.py
FORCE_TRADITIONAL_INJECTION = False
ENABLE_GAME_SUSPENSION = False
ENABLE_PRIORITY_BOOST = False
```

**Test Procedure:**

1. Lock champion early (wait for prebuild to finish)
2. Hover a skin LATE (within last 2 seconds before countdown ends)
3. Prebuild won't be ready → Forces traditional injection
4. Observe if CPU contention provides enough buffer

**Expected Behavior:**

- Traditional injection starts at T=500ms
- Takes ~2-4 seconds
- Game launch starts at T=0ms
- CPU contention slows game opening
- Injection completes before game client fully opens
- Skin appears in game

**Success Criteria:**

- ✅ Works 3/3 times
- ✅ Game opening slowed to 3-5 seconds
- ✅ Skin applied successfully

---

### **Phase 2: Force Traditional Injection**

**Configuration:**

```python
# constants.py
FORCE_TRADITIONAL_INJECTION = True  # ← Enable this
ENABLE_GAME_SUSPENSION = False
ENABLE_PRIORITY_BOOST = False
```

**Test Procedure:**

1. Lock any champion
2. Hover any skin
3. System will SKIP prebuild entirely
4. ALWAYS uses traditional injection
5. Multiple tests with different champions

**Expected Behavior:**

- Every injection uses traditional path (2-4 seconds)
- If it works: Natural CPU contention is sufficient
- If it fails: Need active delay mechanism

**Success Criteria:**

- ✅ Works consistently (5/5 tests)
- ✅ All skins apply successfully
- ✅ No failures due to fast game opening

---

### **Phase 3: Priority Boost (If Phase 2 Fails)**

**Configuration:**

```python
# constants.py
FORCE_TRADITIONAL_INJECTION = True
ENABLE_GAME_SUSPENSION = False
ENABLE_PRIORITY_BOOST = True  # ← Enable this
```

**Test Procedure:**

1. Same as Phase 2
2. Injection processes now run at HIGH priority
3. Game gets less CPU → opens slower
4. More reliable buffer window

**Expected Behavior:**

- Injection processes consume MORE CPU
- Game opening slows from 1s → 3-5s
- More consistent results

---

### **Phase 4: Game Suspension (If Phase 3 Fails)**

**⚠️ WARNING: Use with caution - may trigger anti-cheat**

**Configuration:**

```python
# constants.py
FORCE_TRADITIONAL_INJECTION = True
ENABLE_GAME_SUSPENSION = True  # ← Enable this (RISKY!)
ENABLE_PRIORITY_BOOST = False
```

**Test Procedure:**

1. Same as Phase 2
2. Game process will be SUSPENDED during injection
3. Forcefully delays game opening
4. Most reliable but risky

---

## 📊 Decision Tree

```
Test Phase 1 (Natural)
    ↓
Works reliably?
├─ YES → ✅ App is FINISHED! Ship it!
│         Natural CPU contention is sufficient.
│
└─ NO → Continue to Phase 2

Test Phase 2 (Force Traditional)
    ↓
Works reliably?
├─ YES → ✅ App is FINISHED!
│         Your PC naturally provides buffer.
│
└─ NO → Continue to Phase 3

Test Phase 3 (Priority Boost)
    ↓
Works reliably?
├─ YES → ✅ SHIP with ENABLE_PRIORITY_BOOST = True
│         Artificial CPU contention works.
│
└─ NO → Continue to Phase 4

Test Phase 4 (Game Suspension)
    ↓
Works reliably?
├─ YES → ⚠️ Works but RISKY
│         Consider if worth the anti-cheat risk.
│
└─ NO → ❌ Need different approach
          (Maybe inject even earlier, or optimize injection speed)
```

---

## 🔍 What to Look For in Logs

### Success Pattern:

```
[loadout] T-0s
[inject] Pre-built overlay not ready for KDA Ahri, waiting...
[inject] Pre-building timeout for KDA Ahri, using traditional injection
[inject] starting injection for: KDA Ahri
Injector: Starting injection for: KDA Ahri
Injector: mkoverlay completed in 2.34s - injection applied
[inject] successfully injected: KDA Ahri
[phase] InProgress
```

### Failure Pattern:

```
[loadout] T-0s
[inject] starting injection for: KDA Ahri
[phase] InProgress  ← Game started too fast!
Injector: Starting injection for: KDA Ahri  ← Still building!
Injector: mkoverlay completed in 2.34s  ← Too late!
(Skin doesn't appear in game)
```

---

## 💡 Tips

1. **Test on different champions**

   - Some have more skins (longer prebuild)
   - Some have fewer skins (shorter prebuild)

2. **Test at different hover times**

   - Hover at T-10s (prebuild might finish)
   - Hover at T-2s (prebuild definitely won't finish)
   - Hover at T-0.5s (worst case)

3. **Monitor CPU usage**

   - Use Task Manager to watch:
     - mkoverlay.exe processes
     - League of Legends.exe
     - CPU % for each

4. **Test on different PCs if possible**
   - Fast PC (SSD, 8+ cores): Harder to slow down
   - Slow PC (HDD, 4 cores): Natural buffer easier

---

## 🎯 Goal

If **Phase 1 or 2 succeeds** → Your app is DONE! ✅

- Natural CPU contention is sufficient
- No need for risky process manipulation
- Ship with confidence!

If **Phase 3 succeeds** → Almost done!

- Need priority boost enabled
- Still safe, no process suspension
- Good compromise

If **Phase 4 needed** → Risky territory ⚠️

- Evaluate if worth anti-cheat risk
- Consider alternative approaches
- Maybe optimize injection speed instead

---

## 📝 Next Steps After Testing

1. **Document Results**

   - Which phase succeeded?
   - How consistent? (X/10 success rate)
   - Average game opening time?

2. **Update Constants**

   - Set appropriate flags
   - Document why chosen approach

3. **Final Testing**

   - Test 20+ games
   - Different champions
   - Different times of day (server load)

4. **Ship It!** 🚀
