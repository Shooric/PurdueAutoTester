"""
Bug: the loop never ends.
autotester should say: timeout.

Example execution 1:
Start: -> 3
Done
"""
n = int(input("Start: "))
while n > 0:
    pass
print("Done")
