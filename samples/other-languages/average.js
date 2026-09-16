/*
JavaScript.  Bug: prints the raw float instead of two decimals.
autotester should say: number formatting.

Example execution 1:
First: -> 3
Second: -> 4
The average is 3.50

Example execution 2:
First: -> 10
Second: -> 5
The average is 7.50
*/
const rl = require("readline").createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((res) => rl.question(q, res));
(async () => {
  const a = Number(await ask("First: "));
  const b = Number(await ask("Second: "));
  console.log(`The average is ${(a + b) / 2}`);
  rl.close();
})();
