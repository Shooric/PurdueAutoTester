"""
Average of a list of grades.  Bug: dividing by zero when no grades are entered.
autotester should say: crash, ZeroDivisionError.

Example execution 1:
Grade (or -1 to stop): -> 80
Grade (or -1 to stop): -> 90
Grade (or -1 to stop): -> -1
Average: 85.0

Example execution 2:
Grade (or -1 to stop): -> -1
Average: 0.0
"""
total = count = 0
while True:
    g = int(input("Grade (or -1 to stop): "))
    if g == -1:
        break
    total += g
    count += 1
print(f"Average: {total / count}")
