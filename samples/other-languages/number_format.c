/*
Average of two numbers.  Bug: printf uses %.1f where the example shows 2 decimals.
autotester should say: number formatting, and name the printf line.

Example execution 1:
Enter the first number: -> 3
Enter the second number: -> 4
The average is 3.50

Example execution 2:
Enter the first number: -> 10
Enter the second number: -> 5
The average is 7.50
*/
#include <stdio.h>
int main(void) {
    double a, b;
    printf("Enter the first number: ");
    scanf("%lf", &a);
    printf("Enter the second number: ");
    scanf("%lf", &b);
    printf("The average is %.1f\n", (a + b) / 2);
    return 0;
}
