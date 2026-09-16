/*
No bug: everything matches.

Example execution 1:
Name: -> Tim
Hello, Tim!

Example execution 2:
Name: -> Ana
Hello, Ana!
*/
#include <stdio.h>
int main(void) {
    char name[64];
    printf("Name: ");
    scanf("%63s", name);
    printf("Hello, %s!\n", name);
    return 0;
}
