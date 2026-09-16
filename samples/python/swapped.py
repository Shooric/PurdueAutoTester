"""
Rectangle.  Bug: width and height are printed in the wrong order.
autotester should say: numbers swapped.

Example execution 1:
Width: -> 3
Height: -> 7
A 3 by 7 rectangle has area 21

Example execution 2:
Width: -> 2
Height: -> 5
A 2 by 5 rectangle has area 10
"""
w = int(input("Width: "))
h = int(input("Height: "))
print(f"A {h} by {w} rectangle has area {w * h}")
