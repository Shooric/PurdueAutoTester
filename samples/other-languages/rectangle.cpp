/*
C++.  Area of a rectangle.  Bug: setprecision(1) where the example shows 2 decimals.
One "cin >> width >> height" reads both values from a single typed line.
autotester should say: number formatting, and name the cout line.

Example execution 1:
Width and height: -> 3 7
A 3 by 7 rectangle has area 21.00

Example execution 2:
Width and height: -> 2.5 4
A 2.5 by 4 rectangle has area 10.00
*/
#include <iostream>
#include <iomanip>
using namespace std;

int main() {
    double width, height;
    cout << "Width and height: ";
    cin >> width >> height;
    cout << "A " << width << " by " << height << " rectangle has area "
         << fixed << setprecision(1) << width * height << endl;
    return 0;
}
