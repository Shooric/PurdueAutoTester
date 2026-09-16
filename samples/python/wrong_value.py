"""
Area of a circle.  Bug: pi is 3.
autotester should say: wrong value.

Example execution 1:
Radius: -> 1
Area: 3.14

Example execution 2:
Radius: -> 2
Area: 12.57
"""
r = float(input("Radius: "))
print(f"Area: {3 * r * r:.2f}")
