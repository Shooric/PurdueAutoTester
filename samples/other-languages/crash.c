/*
Sums grades into an array.  Bug: the array pointer is never given any memory,
so the first write crashes.  autotester should say: crash (SIGSEGV).

Example execution 1:
How many grades? -> 2
Grade: -> 80
Grade: -> 90
Total: 170
*/
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    int n, i, total = 0;
    int *grades = NULL;          /* should have been malloc'd */
    printf("How many grades? ");
    scanf("%d", &n);
    for (i = 0; i < n; i++) {
        printf("Grade: ");
        scanf("%d", &grades[i]);
        total += grades[i];
    }
    printf("Total: %d\n", total);
    return 0;
}
