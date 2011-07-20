#!/bin/bash
# Converts all banner*.jpg images into a banner.jpg, avertical strip of images
# that can be scrolled through.

# Remove the original flattened banner. Otherwise montage does recursion.
rm banner.jpg
montage -geometry 1024x125+0+0 -tile 1 -adjoin banner*.jpg banner.jpg
