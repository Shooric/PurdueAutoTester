/*
The ": " marker also appears in this program's OUTPUT, on the Speed and
Distance lines.  Reading the source shows the program only reads twice, and
that those two lines come out of printf whole, so they are not treated as
input.  Bug: the speed is printed with one decimal instead of two.

Example execution 1:
Enter the distance: 100
Enter the time: 4
Distance: 100.00
Speed: 25.00

Example execution 2:
Enter the distance: 90
Enter the time: 3
Distance: 90.00
Speed: 30.00
*/
#include <stdio.h>
int main(void) {
    float distance, t;
    printf("Enter the distance: ");
    scanf("%f", &distance);
    printf("Enter the time: ");
    scanf("%f", &t);
    printf("Distance: %.2f\n", distance);
    printf("Speed: %.1f\n", distance / t);
    return 0;
}
