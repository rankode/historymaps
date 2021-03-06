#!/usr/bin/env python
import winkel
import math
import json
import sys

pi = math.pi

w = winkel.ScaledWinkel(25201, 15120, +11.0)


def explore_winkel():
    w = winkel.Winkel()
    def show(Lambda, phi):
        x, y = w.project(Lambda, phi)
        print "%s, %s -> %s, %s" % (Lambda, phi, x, y)
    show(-pi, 0.0)
    show(+pi, 0.0)
    show(0.0, -pi/2)
    show(0.0, +pi/2)
    show(-pi, -pi/2)
    show(+pi, -pi/2)
    show(-pi, +pi/2)
    show(+pi, +pi/2)

    # Range is: x \in [-2.57079632679, 2.57079632679]
    #           y \in [-pi/2, +pi/2]

# Number of numbers expected after each movement command in a 'd' string.
MOVEMENT_SIZES = {
    'M': 2,
    'L': 2,
    'S': 4,
    'l': 2,
}


def chunks(xs, num):
    '''Split a list into chunks of size `num`.'''
    for i in xrange(0, len(xs), num):
        yield xs[i:i+num]


def parse_draw_string(string):
    parts = string.strip().split(' ')

    def lookahead_numbers(index):
        '''Return all the numbers in a row after this index.'''
        r = []
        index += 1
        while index < len(parts):
            try:
                r.append(int(parts[index]))
            except ValueError:
                break
            index += 1
        return r

    i = 0
    tuples = []
    while i < len(parts):
        part = parts[i]
        if part in ['M', 'L', 'S', 'l']:
            nums = lookahead_numbers(i)
            size = MOVEMENT_SIZES[part]
            assert len(nums) % size == 0, (
                'Movement %s should have a multiple of %d numbers after it; got %d' % (
                    part, len(nums), size))
            for chunk in chunks(nums, size):
                tuples.append((part, chunk))
            i += 1 + len(nums)
            # 2,145 paths have "l" relative line movements
            # 0 paths have "s" or "m" movements
        elif part == 'z':
            tuples.append(('z', []))
            i += 1
        else:
            raise ValueError('Unknown command: "%s" in %s' % (part, string))

    return tuples


def serialize_path(path):
    '''Convert a parsed path back into an SVG 'd' string.'''
    return ' '.join('%s %s' % (motion, ' '.join(str(x) for x in coords))
                    for motion, coords in path).strip()


def absolutize_path(path):
    '''Replace all "l" relative movements with "L" absolute movements.'''
    pos = None  # current position
    new_path = []
    for segment in path:
        motion, coords = segment
        if motion == 'l':
            pos = [pos[0] + coords[0], pos[1] + coords[1]]
            new_path.append(('L', pos))
            continue

        if motion in ('M', 'L'):
            pos = coords
        elif motion == 'S':
            pos = coords[3:4]  # controlX, controlY, x, y
        new_path.append(segment)

    return new_path


def interpolate_cubic(x1, y1, x2, y2, x3, y3, x4, y4, num_points):
    # See https://en.wikipedia.org/wiki/B%C3%A9zier_curve#Cubic_B.C3.A9zier_curves
    for i in xrange(0, num_points):
        t = 1.0 * i / (num_points - 1)
        a1 = (1 - t) ** 3
        a2 = 3 * t * (1 - t) ** 2
        a3 = 3 * (1 - t) * t ** 2
        a4 = t ** 3
        x = a1 * x1 + a2 * x2 + a3 * x3 + a4 * x4
        y = a1 * y1 + a2 * y2 + a3 * y3 + a4 * y4
        yield (x, y)


def interpolate_curves(path, num_points=8):
    '''Replace all 'S' movements with approximating 'L' movements.'''
    pos = None  # current position
    prev_control = None
    new_path = []
    for segment in path:
        motion, coords = segment
        if motion == 'S':
            px, py = pos
            cx2, cy2, x, y = coords
            if prev_control:
                # the other control point is the previous control, flipped over (px, py)
                pcx, pcy = prev_control
                cx1 = px + (px - pcx)
                cy1 = py + (py - pcy)
            else:
                # the other control point _is_ (px, py)
                cx1, cy1 = px, py
            # print('p1: (%s, %s) c1: (%s, %s) c2: (%s, %s) p2: (%s, %s)' % (
            #    px, py, cx1, cy1, cx2, cy2, x, y))

            for pt in interpolate_cubic(px, py, cx1, cy1, cx2, cy2, x, y, num_points=num_points):
                new_path.append(('L', pt[:]))

            prev_control = cx2, cy2
            pos = x, y
            continue

        if motion in ('M', 'L'):
            pos = coords
            prev_control = None
        new_path.append(segment)
    return new_path


def extremes_from_path(path):
    '''Return ((minx, miny), (maxx, maxy)) from a parsed path.'''
    minx = 1e9
    miny = 1e9
    maxx = -1e9
    maxy = -1e9
    for motion, coords in path:
        for i in range(0, len(coords), 2):
            x = coords[i]
            y = coords[i + 1]
            minx = min(x, minx)
            miny = min(y, miny)
            maxx = max(x, maxx)
            maxy = max(y, maxy)
    return ((minx, miny), (maxx, maxy))


def motions_to_lng_lats(motions):
    '''Motions is a parse d= string. Converts x,y to lat,lon.'''
    out_motions = []
    for motion, coords in motions:
        lls = []
        for i in range(0, len(coords), 2):
            x = coords[i]
            y = coords[i + 1]
            lon, lat = w.invert(x, y)
            lls.append(lon)
            lls.append(lat)
        out_motions.append((motion, lls))
    return out_motions


def flip_coords(motions):
    '''Motions is a parsed SVG path. This replaces y with -y.'''
    out_motions = []
    for motion, coords in motions:
        out = []
        for i in range(0, len(coords), 2):
            out.append(coords[i])
            out.append(-coords[i + 1])
        out_motions.append((motion, out))
    return out_motions


def path_to_coords(path):
    '''Convert a parsed path to a GeoJSON-style coordinates array.'''
    all_groups = []
    this_group = None
    for motion, coords in path:
        if motion == 'M':
            if this_group:
                all_groups.append(this_group)
            this_group = [coords]
        elif motion == 'z':
            this_group.append(this_group[0])
        else:
            this_group.append(coords)
    if this_group:
        all_groups.append(this_group)
    return all_groups


def shape_to_coords(d):
    '''Convert an SVG path string to a GeoJSON-style coordinates array.'''
    path = parse_draw_string(d)
    path = absolutize_path(path)
    path = interpolate_curves(path)
    # path = motions_to_lng_lats(path)
    path = flip_coords(path)
    return path_to_coords(path)


def convert_countries_js():
    raw_js = open('several_countries.js').read()
    data = json.loads(raw_js[raw_js.index('['):raw_js.index('\n')])

    out = []
    for year, nations in data:
        out_nations = {}
        for name, coords in nations.iteritems():
            if not coords:
                out_nations[name] = coords
            else:
                motions = parse_draw_string(coords)
                out_nations[name] = motions_to_lng_lats(motions)

        # Something isn't quite right here -- Sparta is ~10 degrees shifted
        # Also have really short polygons (2 points) for Russia at the end
        sys.stderr.write('Done with %s\n' % year)
        out.append((year, out_nations))

    print json.dumps(out)
    # viewBox="0 0 25201 15120"


if __name__ == '__main__':
    for idx, line in enumerate(open('coords.tsv')):
        line = line.strip()
        if idx == 0:
            print '\t'.join([line] + ['invLat', 'invLon', 'dLat', 'dLon', 'rmse'])
            continue

        y, x, lat, lon = [float(v) for v in line.split('\t')]
        inv_lon, inv_lat = w.invert(x, y)
        dLat = inv_lat - lat
        dLon = inv_lon - lon
        rmse = math.sqrt(dLat ** 2 + dLon ** 2)

        print '\t'.join([line] + [str(x) for x in (inv_lat, inv_lon, dLat, dLon, rmse)])
