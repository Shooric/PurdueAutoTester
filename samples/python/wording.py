"""
Age next year.  Bug: the sentence is worded differently from the example.
autotester should say: wording.

Example execution 1:
How old are you? -> 20
Next year you will be 21

Example execution 2:
How old are you? -> 7
Next year you will be 8
"""
age = int(input("How old are you? "))
print(f"You will turn {age + 1} next year")
