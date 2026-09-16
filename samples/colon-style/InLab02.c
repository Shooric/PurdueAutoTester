/*=======================================================
 Programmer: Your full name
 Email: Your email address
 CNIT 105, InLab02

 Program Description: reads a few values and prints them back.
 Academic Honesty: I attest that this is my original work.
=========================================================*/
/*
Transcripts in the CNIT 105 style: what the user types follows the prompt's
": ", so this file is tested with   --input-marker ': '
Note "Enter base and height of a triangle: 5 11" answers one scanf that reads
two values from a single typed line.

Example execution 1:
**********************************
* <Name>                         *
* <Email ID>                     *
* CNIT105 InLab02                *
**********************************

Enter the number of students in CNIT 105: 230
The number of students in CNIT105 is 230

Enter the price of the textbook: 78.65
The price of the textbook is $78.65

Enter base and height of a triangle: 5 11
Area of a triangle with base 5.00 and height 11.00 is 27.50

Enter the distance car has travelled (in miles): 165
Enter the time it has travelled (in hours): 4
The speed of the car is 41.25 miles per hour

Example execution 2:
**********************************
* <Name>                         *
* <Email ID>                     *
* CNIT105 InLab02                *
**********************************

Enter the number of students in CNIT 105: 40
The number of students in CNIT105 is 40

Enter the price of the textbook: 12.5
The price of the textbook is $12.50

Enter base and height of a triangle: 3 4
Area of a triangle with base 3.00 and height 4.00 is 6.00

Enter the distance car has travelled (in miles): 100
Enter the time it has travelled (in hours): 2
The speed of the car is 50.00 miles per hour
*/
#include <stdio.h>

int main(void) {
    int numStudents;
    float price, base, height, area, distance, time, speed;

    printf("**********************************\n");
    printf("* <Name>                         *\n");
    printf("* <Email ID>                     *\n");
    printf("* CNIT105 InLab02                *\n");
    printf("**********************************\n\n");

    printf("Enter the number of students in CNIT 105: ");
    scanf("%d", &numStudents);
    printf("The number of students in CNIT105 is %d\n\n", numStudents);

    printf("Enter the price of the textbook: ");
    scanf("%f", &price);
    printf("The price of the textbook is $%.2f\n\n", price);

    printf("Enter base and height of a triangle: ");
    scanf("%f %f", &base, &height);
    area = 0.5f * base * height;
    printf("Area of a triangle with base %.2f and height %.2f is %.2f\n\n", base, height, area);

    printf("Enter the distance car has travelled (in miles): ");
    scanf("%f", &distance);
    printf("Enter the time it has travelled (in hours): ");
    scanf("%f", &time);
    speed = distance / time;
    printf("The speed of the car is %.2f miles per hour\n", speed);
    return 0;
}
