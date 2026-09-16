# Ruby.  Bug: the sentence is worded differently from the example.
# autotester should say: wording, and name the puts line.
#
# Example execution 1:
# What is your name? -> Tim
# Nice to meet you, Tim!
#
# Example execution 2:
# What is your name? -> Ana
# Nice to meet you, Ana!
$stdout.sync = true
print "What is your name? "
name = gets.chomp
puts "Hello there, #{name}!"
