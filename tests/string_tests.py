name = "tom" # a string
mychar = 'a' # a character
name2 = str("newstring")
number = "1"
print number.zfill(3), "<br>"
s = "welcome to python"
print s, "<br>"
print "s.isalnum()", s.isalnum(), "<br>"
print "s.isalpha()", s.isalpha(), "<br>"
print '"2012".isdigit()', "2012".isdigit(), "<br>"
print "s.islower()", s.islower(), "<br>"
s = s.upper()
print "s after s.upper()", s, "<br>"
print "s.islower()", s.islower(), "<br>"
print "s.isupper()", s.isupper(), "<br>"
print '"WELCOME".isupper()', "WELCOME".isupper(), "<br>"
print '"  \t".isspace()', "  \t".isspace(), "<br>"
s = "welcome to python"
print "s", s, "<br>"
print 's.endswith("thon")', s.endswith("thon"), "<br>"
print 's.startswith("good")', s.startswith("good"), "<br>"
print 's.find("come")', s.find("come"), "<br>"
print 's.find("become")', s.find("become"), "<br>"
print 's.find("o")', s.find("o"), "<br>"
print 's.rfind("o")', s.rfind("o"), "<br>"
print 's.count("o")', s.count("o"), "<br>"
s = "string in python"
print "s", s, "<br>"
print 's.capitalize()', s.capitalize(), "<br>"
print 's.index("n")', s.index("n"), "<br>"
print 's.rindex("n")', s.rindex("n"), "<br>"
s = "This Is Test"
print "s", s, "<br>"
print 's.lower()', s.lower(), "<br>"
print 's.upper()', s.upper(), "<br>"
print 's.swapcase()', s.swapcase(), "<br>"
print 's.center(30)', s.center(30), "<br>"
s6 = s.replace("Is", "Was")
print 's6 after s6 = s.replace("Is", "Was")', s6, "<br>"
print "s", s, "<br>"
s = "This Is Test\n"
print "s", s, "<br>"
s1 = s.strip()
print "s1 = s.strip()", s1, ";", "<br>"
s = "    string in python   "
print "s", s, "<br>"
print "s.rstrip()", s.rstrip(), "<br>"
print "s.lstrip()", s.lstrip(), "<br>"
s = s.strip()
print "s after s.strip()", s, "<br>"
elements = s.split(" ")
print "elements = s.split(" ")", elements, "<br>"
for i in range(3):
	print "elements[i]", elements[i], "<br>"
newstring = " ".join(elements)
print 'newstring = " ".join(elements)', newstring, "<br>"
lines = "hello\nmy name is\nMonty"
arr = lines.splitlines()
print "lines.splitlines()", arr, "<br>"
for i, elem in enumerate(arr):
	print i, elem, "<br>"
for i in range(10):
	print i,
print "<br>"
for i in arr:
	print i, "<br>"
