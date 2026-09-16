/*
Price per item.  Bug: integer division.
autotester should say: integer division.

Example execution 1:
Total price: -> 10
Number of items: -> 4
Each item costs 2.5

Example execution 2:
Total price: -> 7
Number of items: -> 2
Each item costs 3.5
*/
#include <stdio.h>
int main(void) {
    int total, n;
    printf("Total price: ");
    scanf("%d", &total);
    printf("Number of items: ");
    scanf("%d", &n);
    printf("Each item costs %d\n", total / n);
    return 0;
}
