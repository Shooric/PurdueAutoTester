/*
Java.  Bug: the greeting is lower case.
autotester should say: letter case.

Example execution 1:
Name: -> Tim
Hello, Tim!

Example execution 2:
Name: -> Ana
Hello, Ana!
*/
import java.util.Scanner;

public class Greeter {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        System.out.print("Name: ");
        String name = in.nextLine();
        System.out.println(("Hello, " + name + "!").toLowerCase());
    }
}
