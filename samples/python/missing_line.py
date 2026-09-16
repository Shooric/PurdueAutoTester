"""
Countdown.  Bug: the last line is never printed.
autotester should say: missing line.

Example execution 1:
Start: -> 3
3
2
1
Liftoff!

Example execution 2:
Start: -> 1
1
Liftoff!
"""
n = int(input("Start: "))
for i in range(n, 0, -1):
    print(i)
