import time

# --- 1. Naive Recursive Approach ---
# Time Complexity: O(2^n) - Exponential
# Space Complexity: O(n) - Due to recursion depth
def fib_naive(n):
    if n <= 1:
        return n
    return fib_naive(n - 1) + fib_naive(n - 2)


# --- 2. Dynamic Programming: Memoization (Top-Down) ---
# Time Complexity: O(n) - Linear
# Space Complexity: O(n) - For the memo and recursion depth
def fib_memo(n, memo={}):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    
    result = fib_memo(n - 1, memo) + fib_memo(n - 2, memo)
    memo[n] = result
    return result


# --- 3. Dynamic Programming: Tabulation (Bottom-Up) ---
# Time Complexity: O(n) - Linear
# Space Complexity: O(n) - For the table
def fib_tabulation(n):
    if n <= 1:
        return n
    
    table = [0] * (n + 1)
    table[1] = 1
    
    for i in range(2, n + 1):
        table[i] = table[i - 1] + table[i - 2]
        
    return table[n]

# --- Bonus: Space-Optimized Tabulation ---
# Time Complexity: O(n) - Linear
# Space Complexity: O(1) - Constant
def fib_optimized(n):
    if n <= 1:
        return n
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
        
    return b


# --- Main execution block to demonstrate and compare ---
if __name__ == "__main__":
    # n = 35 is a good middle ground to see the performance difference.
    n_val = 35

    print("--- Dynamic Programming Demonstration using Fibonacci ---")
    print(f"Calculating fib({n_val})...\n")

    # --- Test Naive Approach ---
    print("1. Naive Recursive Approach (will be slow)...")
    start_time = time.time()
    result_naive = fib_naive(n_val)
    end_time = time.time()
    print(f"   Result: {result_naive}")
    print(f"   Time taken: {end_time - start_time:.4f} seconds\n")

    # --- Test Memoization Approach ---
    print("2. DP with Memoization (Top-Down)...")
    start_time = time.time()
    result_memo = fib_memo(n_val, {})
    end_time = time.time()
    print(f"   Result: {result_memo}")
    print(f"   Time taken: {end_time - start_time:.6f} seconds\n")

    # --- Test Tabulation Approach ---
    print("3. DP with Tabulation (Bottom-Up)...")
    start_time = time.time()
    result_tab = fib_tabulation(n_val)
    end_time = time.time()
    print(f"   Result: {result_tab}")
    print(f"   Time taken: {end_time - start_time:.6f} seconds\n")

    # --- Test Optimized Tabulation Approach ---
    print("4. Space-Optimized Tabulation...")
    start_time = time.time()
    result_opt = fib_optimized(n_val)
    end_time = time.time()
    print(f"   Result: {result_opt}")
    print(f"   Time taken: {end_time - start_time:.6f} seconds\n")