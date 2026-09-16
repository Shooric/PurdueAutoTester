/*
Bug: asks for a third number the example never provides.
autotester should say: input mismatch.

Example execution 1:
First: -> 1
Second: -> 2
Sum: 3
*/
#include <stdio.h>
int main(void) {
    int a, b, c;
    printf("First: ");
    scanf("%d", &a);
    printf("Second: ");
    scanf("%d", &b);
    printf("Third: ");
    scanf("%d", &c);
    printf("Sum: %d\n", a + b);
    return 0;
}
