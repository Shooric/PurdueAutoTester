"""
Average of two numbers.  Bug: the float is printed without formatting.
autotester should say: number formatting, print with 2 decimal places.

Example execution 1:
Enter the first number: -> 3
Enter the second number: -> 4
The average is 3.50

Example execution 2:
Enter the first number: -> 10
Enter the second number: -> 5
The average is 7.50

Example execution 3:
Enter the first number: -> 2
Enter the second number: -> 2
The average is 2.00
"""
a = int(input("Enter the first number: "))
b = int(input("Enter the second number: "))
print(f"The average is {(a + b) / 2}")
