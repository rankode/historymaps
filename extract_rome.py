#!/usr/bin/python

import db
import sys
import re
import json
from collections import defaultdict

num_countries = 1000
end_year = 2010

shapes = db.ShapesDb()

countries = [c[0] for c in shapes.countries_by_span(limit_year=end_year)[:num_countries]]

country_colors = defaultdict(str)  # name -> color string
for name in countries:
  country_colors[name] = shapes.color_for_country(name)

country_shapes = {}  # name -> year -> shape

for name in countries:
  key_shapes = shapes.shapes_for_country(name)
  if name not in country_shapes:
    country_shapes[name] = {}

  data = country_shapes[name]  # year -> shape
  for year, shape in key_shapes:
    if year not in data:
      data[year] = shape
    else:
      assert (data[year] == '' or shape == '')
      if shape:
        data[year] = shape



# go through and add a blank in the year before an empire comes into existence.
# this is more complicated than you'd think because some empires (e.g.
# Byzantium) come and go.
for name, data in country_shapes.iteritems():
  #first_year, last_year = min(data.keys()), max(data.keys())
  last_shape = ''
  blank_years_to_add = []
  for year in sorted(data.keys()):
    shape = data[year]
    if last_shape == '' and shape != '':
      blank_years_to_add.append(year - 1)
    last_shape = shape

  for year in blank_years_to_add:
    data[year] = ''


hash_data = defaultdict(lambda : defaultdict(str))  # year -> name -> shape
for name, data in country_shapes.iteritems():
  hash_data[min(data.keys()) - 1][name] = ''  # year before it existed.
  for year, shape in data.iteritems():
    hash_data[year][name] = shape


array_data = []
for year in sorted(hash_data.keys()):
  array_data.append([year, hash_data[year]])

print 'var rome = ',
print json.dumps(array_data, separators=(',',':'))

print 'var colors = ',
print json.dumps(country_colors, separators=(',',':'))

print 'var end_year = %d;' % end_year
