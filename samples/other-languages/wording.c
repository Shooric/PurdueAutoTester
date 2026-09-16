/*
Age next year.  Bug: the sentence is worded differently.
autotester should say: wording, and name the printf line.

Example execution 1:
How old are you? -> 20
Next year you will be 21

Example execution 2:
How old are you? -> 7
Next year you will be 8
*/
#include <stdio.h>
int main(void) {
    int age;
    printf("How old are you? ");
    scanf("%d", &age);
    printf("You will turn %d next year\n", age + 1);
    return 0;
}
