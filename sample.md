**Fixed Input** (column 2):
- Integer input `0` → real value by dividing by 2^|lsbIn| = 2^3 = 8
- `0 / 8 = 0.00000`

**Expected** (column 5):
- Evaluate the function with the fixed input
- `log(0.0 + 0.1) / log(2) = log(0.1) / log(2) ≈ -3.32193`

**Fixed Output** (column 4):
- Integer output `-27` → real value by multiplying by 2^lsbOut = 2^-3 = 1/8 = 0.125
- `-27 × 0.125 = -3.37500`

**ABS ERROR** (column 6):
- Difference between Fixed Output and Expected
- `-3.37500 - (-3.32193) = -0.05307`

**Why this matters:**
- The hardware outputs integers (e.g., `-27`)
- We convert to real values (e.g., `-3.37500`) to compare with the math result (e.g., `-3.32193`)
- The error shows how close the hardware result is to the expected value

**Example for input=1:**
- Fixed Input: `1 / 8 = 0.12500`
- Expected: `log(0.125 + 0.1) / log(2) ≈ -2.15200`
- Fixed Output: `-17 × 0.125 = -2.12500`
- Error: `-2.12500 - (-2.15200) = 0.02700` (hardware is slightly higher)