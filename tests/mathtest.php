<?php set_include_path(get_include_path() . PATH_SEPARATOR . dirname(__FILE__) . DIRECTORY_SEPARATOR . 'libpy2php');
require_once('libpy2php.php');
function modf($zahl) {
    return [$zahl-pyjslib_int($zahl), pyjslib_int($zahl)];
} 
pyjslib_printnl(M_PI);
pyjslib_printnl(M_E);
pyjslib_printnl(sqrt(2.0));
pyjslib_printnl(sin(deg2rad(90)));


