"""
Price per item.  Bug: uses // instead of /.
autotester should say: integer division.

Example execution 1:
Total price: -> 10
Number of items: -> 4
Each item costs 2.5

Example execution 2:
Total price: -> 7
Number of items: -> 2
Each item costs 3.5
"""
total = int(input("Total price: "))
n = int(input("Number of items: "))
print(f"Each item costs {total // n}")
