#!/usr/bin/python

from BeautifulSoup import BeautifulSoup
import re
import whm


#ordered_files = whm.ordered_map_files()
fs = whm.all_ordered_map_files()

#fs = [f for f in fs if whm.filename_to_year(f) >= 1763]

for f in fs:
  svg = whm.SvgFile(f)
  print '%+4d: %d' % (svg.year(), len(svg.countries()))

