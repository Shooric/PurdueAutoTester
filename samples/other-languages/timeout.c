/*
Bug: the loop never ends.
autotester should say: timeout.

Example execution 1:
Start: -> 3
Done
*/
#include <stdio.h>
int main(void) {
    int n;
    printf("Start: ");
    scanf("%d", &n);
    while (n > 0) { }
    printf("Done\n");
    return 0;
}
