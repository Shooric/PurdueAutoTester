"""
Greeting.  Bug: the greeting is all lower case.
autotester should say: letter case.

Example execution 1:
What is your name? -> Tim
Hello, Tim!

Example execution 2:
What is your name? -> Ana
Hello, Ana!
"""
name = input("What is your name? ")
print(f"hello, {name}!".lower())
