/*
Countdown.  Bug: the last line is never printed.
autotester should say: missing line.

Example execution 1:
Start: -> 3
3
2
1
Liftoff!
*/
#include <stdio.h>
int main(void) {
    int n, i;
    printf("Start: ");
    scanf("%d", &n);
    for (i = n; i > 0; i--) printf("%d\n", i);
    return 0;
}
