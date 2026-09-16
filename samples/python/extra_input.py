"""
Adds two numbers.  Bug: asks for a third number the example never provides.
autotester should say: input mismatch.

Example execution 1:
First: -> 1
Second: -> 2
Sum: 3
"""
a = int(input("First: "))
b = int(input("Second: "))
c = int(input("Third: "))
print(f"Sum: {a + b}")
