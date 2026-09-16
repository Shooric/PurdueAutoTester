/*
Rust.  Speed of a car.  Bug: integer division throws the remainder away.
autotester should say: integer division, with Rust advice.

Example execution 1:
Distance in miles: -> 165
Time in hours: -> 4
The speed is 41.25 miles per hour

Example execution 2:
Distance in miles: -> 100
Time in hours: -> 8
The speed is 12.5 miles per hour
*/
use std::io::{self, Write};

fn ask(prompt: &str) -> i64 {
    print!("{}", prompt);
    io::stdout().flush().unwrap();
    let mut line = String::new();
    io::stdin().read_line(&mut line).unwrap();
    line.trim().parse().unwrap()
}

fn main() {
    let distance = ask("Distance in miles: ");
    let time = ask("Time in hours: ");
    println!("The speed is {} miles per hour", distance / time);
}
