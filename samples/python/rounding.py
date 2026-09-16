"""
Splits a bill.  Bug: truncates to two decimals instead of rounding.
autotester should say: rounding.

Example execution 1:
Bill: -> 8
People: -> 3
Each pays 2.67

Example execution 2:
Bill: -> 10
People: -> 3
Each pays 3.33

Example execution 3:
Bill: -> 20
People: -> 6
Each pays 3.33
"""
bill = float(input("Bill: "))
people = int(input("People: "))
share = int(bill / people * 100) / 100
print(f"Each pays {share:.2f}")
