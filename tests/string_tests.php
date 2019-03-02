<?php set_include_path(get_include_path() . PATH_SEPARATOR . dirname(__FILE__) . DIRECTORY_SEPARATOR . 'libpy2php');
require_once('libpy2php.php');
$name = 'tom';
$mychar = 'a';
$name2 = pyjslib_str('newstring');
$number = '1';
pyjslib_printnl([str_pad($number, 3, '0', STR_PAD_LEFT), '<br>'], true);
$s = 'welcome to python';
pyjslib_printnl([$s, '<br>'], true);
pyjslib_printnl(['s.isalnum()', ctype_alnum($s), '<br>'], true);
pyjslib_printnl(['s.isalpha()', ctype_alpha($s), '<br>'], true);
pyjslib_printnl(['"2012".isdigit()', ctype_digit('2012'), '<br>'], true);
pyjslib_printnl(['s.islower()', ctype_lower($s), '<br>'], true);
$s = strtoupper($s);
pyjslib_printnl(['s after s.upper()', $s, '<br>'], true);
pyjslib_printnl(['s.islower()', ctype_lower($s), '<br>'], true);
pyjslib_printnl(['s.isupper()', ctype_upper($s), '<br>'], true);
pyjslib_printnl(['"WELCOME".isupper()', ctype_upper('WELCOME'), '<br>'], true);
pyjslib_printnl(['"  \t".isspace()', ctype_space('  \t'), '<br>'], true);
$s = 'welcome to python';
pyjslib_printnl(['s', $s, '<br>'], true);
pyjslib_printnl(['s.endswith("thon")', (substr($s, -strlen('thon')) === 'thon'), '<br>'], true);
pyjslib_printnl(['s.startswith("good")', (strpos($s, 'good') === 0), '<br>'], true);
pyjslib_printnl(['s.find("come")', strpos($s, 'come'), '<br>'], true);
pyjslib_printnl(['s.find("become")', strpos($s, 'become'), '<br>'], true);
pyjslib_printnl(['s.find("o")', strpos($s, 'o'), '<br>'], true);
pyjslib_printnl(['s.rfind("o")', strrpos($s, 'o'), '<br>'], true);
pyjslib_printnl(['s.count("o")', substr_count($s, 'o'), '<br>'], true);
$s = 'string in python';
pyjslib_printnl(['s', $s, '<br>'], true);
pyjslib_printnl(['s.capitalize()', ucfirst($s), '<br>'], true);
pyjslib_printnl(['s.index("n")', strpos($s, 'n'), '<br>'], true);
pyjslib_printnl(['s.rindex("n")', strrpos($s, 'n'), '<br>'], true);
$s = 'This Is Test';
pyjslib_printnl(['s', $s, '<br>'], true);
pyjslib_printnl(['s.lower()', strtolower($s), '<br>'], true);
pyjslib_printnl(['s.upper()', strtoupper($s), '<br>'], true);
pyjslib_printnl(['s.swapcase()', strtr($s, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'), '<br>'], true);
pyjslib_printnl(['s.center(30)', str_pad($s, 30, STR_PAD_BOTH), '<br>'], true);
$s6 = str_replace('Is', 'Was', $s);
pyjslib_printnl(['s6 after s6 = s.replace("Is", "Was")', $s6, '<br>'], true);
pyjslib_printnl(['s', $s, '<br>'], true);
$s = 'This Is Test\n';
pyjslib_printnl(['s', $s, '<br>'], true);
$s1 = trim($s);
pyjslib_printnl(['s1 = s.strip()', $s1, ';', '<br>'], true);
$s = '    string in python   ';
pyjslib_printnl(['s', $s, '<br>'], true);
pyjslib_printnl(['s.rstrip()', rtrim($s), '<br>'], true);
pyjslib_printnl(['s.lstrip()', ltrim($s), '<br>'], true);
$s = trim($s);
pyjslib_printnl(['s after s.strip()', $s, '<br>'], true);
$elements = explode(' ', $s);
pyjslib_printnl(['elements = s.split()', $elements, '<br>'], true);
foreach( pyjslib_list(pyjslib_range(3)) as $i ) {
    pyjslib_printnl(['elements[i]', $elements[$i], '<br>'], true);
}
$newstring = join(' ', $elements);
pyjslib_printnl(['newstring = " ".join(elements)', $newstring, '<br>'], true);
$lines = 'hello\nmy name is\nMonty';
$arr = explode('\n', $lines);
pyjslib_printnl(['lines.splitlines()', $arr, '<br>'], true);
foreach( pyjslib_list($arr) as $i => $elem) {
    pyjslib_printnl([$i, $elem, '<br>'], true);
}
foreach( pyjslib_list(pyjslib_range(10)) as $i ) {
    pyjslib_print($i);
}
pyjslib_printnl('<br>');
foreach( pyjslib_list($arr) as $i ) {
    pyjslib_printnl([$i, '<br>'], true);
}


