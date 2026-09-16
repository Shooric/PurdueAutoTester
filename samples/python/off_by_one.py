"""
Counts numbers until the word done.  Bug: the counter starts at 1.
autotester should say: off by one.

Example execution 1:
Number (or done): -> 4
Number (or done): -> 8
Number (or done): -> 15
Number (or done): -> done
You entered 3 numbers

Example execution 2:
Number (or done): -> done
You entered 0 numbers
"""
count = 1
while input("Number (or done): ") != "done":
    count += 1
print(f"You entered {count} numbers")
