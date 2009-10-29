#!/usr/bin/perl -w
#
#  This file extracts content from old html files,
#  and creates a page with the old content and the
#  new style.

use CGI qw(:standard :cgi-lib *table);
use CGI::Pretty;

require "/var/www/hydro/cgi/print_cchdo.pl";

my $file = shift;
open($fh,$file);
open($html,">$file.new");

@file = <$fh>;
$collect =0;
foreach (@file)
{
   if(/begin content/i) { $collect =1; }

   if(/end content/i){$collect = 0;}

   if($collect eq 1)
   {
      push @content,$_;
   }
}

print $html start_html(-title=>"CCHDO Manuals", -style=>{-src=>"http://cchdo.ucsd.edu/style.css"});
print_header($html);
print $html br,br;
print $html start_table();

foreach (@content)
{
   print $html $_,"\n";
}
print $html end_table;
print $html end_html;
close $html
