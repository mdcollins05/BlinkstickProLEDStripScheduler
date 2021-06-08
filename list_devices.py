#!/usr/bin/env python2

from blinkstick import blinkstick

devices = blinkstick.find_all()
for device in devices:
  print("{0}: {1}").format(device.get_description(), device.get_serial())

