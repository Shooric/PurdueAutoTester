# Ruby.  Splitting a bill.  Bug: prints one decimal where the example shows two.
# autotester should say: number formatting.
#
# Example execution 1:
# Bill: -> 20
# People: -> 8
# Each person pays 2.50
#
# Example execution 2:
# Bill: -> 30
# People: -> 4
# Each person pays 7.50
$stdout.sync = true
print "Bill: "
bill = gets.to_f
print "People: "
people = gets.to_i
puts "Each person pays %.1f" % (bill / people)
