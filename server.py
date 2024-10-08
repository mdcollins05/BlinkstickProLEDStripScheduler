#!/usr/bin/env python3

import argparse
import datetime
import os.path
import re
import sys
import yaml
import schedule
import time

from colour import Color
from blinkstick import blinkstick

from threading import Thread

timeRegex = re.compile("^[0-9]{1,2}:[0-9]{2}$")
timespanRegex = re.compile("^[0-9]{1,2}:[0-9]{2}-[0-9]{1,2}:[0-9]{2}$")

def load_schedule(configpath):
  configFile = open(configpath)
  data = yaml.safe_load(configFile)
  configFile.close()
  return data

def natural_gradient(start, end, steps):
  return list(Color(start).range_to(Color(end), steps))

def linear_gradient(start, end, steps):
  '''returns a gradient list of (n) colors between
    two hex colors. startHex and endHex
    should be the full six-digit color string,
    inlcuding the number sign ("#FFFFFF")
    Original from https://bsou.io/posts/color-gradients-with-python
    Modified for my purposes'''

  startHex = hex_to_RGB(Color(start).hex_l)
  endHex = hex_to_RGB(Color(end).hex_l)

  # Initilize a list of the output colors with the starting color
  RGBList = [RGB_to_hex(startHex)]

  # Calcuate a color at each evenly spaced value of t from 1 to steps
  for step in range(1, steps):
    # Interpolate RGB vector for color at the current value of t
    currVector = [
      int(startHex[j] + (float(step)/(steps-1))*(endHex[j]-startHex[j]))
      for j in range(3)
    ]
    # Add it to our list of output colors
    RGBList.append(RGB_to_hex(currVector))

  return RGBList

def swap_r_and_g(hex):
  color = Color(hex)
  return Color(rgb=(color.green, color.red, color.blue))

def hex_to_RGB(hex):
  color = Color(hex)
  return (int(color.red * 255), int(color.green * 255), int(color.blue * 255))

def RGB_to_hex(rgb):
  color = Color(rgb=(rgb[0]/float(255), rgb[1]/float(255), rgb[2]/float(255)))
  return color.hex_l

def get_current_schedule_entries(config, time):
  entries = []
  for entry in config['schedule']:
    if timeRegex.match(entry['time']):
      splitEntryTime = entry['time'].split(":")
      timeToCompare = int(splitEntryTime[0])*60 + int(splitEntryTime[1])
      if time == timeToCompare:
        entries.append(entry)

    if timespanRegex.match(entry['time']):
      splitEntryTimes = entry['time'].split("-")
      splitEntryTimeStart = splitEntryTimes[0].split(":")
      splitEntryTimeEnd = splitEntryTimes[1].split(":")
      timeToCompareStart = int(splitEntryTimeStart[0])*60 + int(splitEntryTimeStart[1])
      timeToCompareEnd = int(splitEntryTimeEnd[0])*60 + int(splitEntryTimeEnd[1])
      if time >= timeToCompareStart and time <= timeToCompareEnd:
        newEntry = dict(entry)
        newEntry['start'] = timeToCompareStart
        newEntry['end'] = timeToCompareEnd
        entries.append(newEntry)
  return entries

def set_color(device, color, morph, dryrun, verbose):
  if not isinstance(color, Color):
    color = Color(color)

  visualColor = color.hex_l

  if 'swap_r_and_g' in device:
    if device['swap_r_and_g']:
      color = swap_r_and_g(color.hex_l)

  RGBColor = color.hex_l
  if not dryrun:
    if morph:
      device['blink_device'].morph(hex=RGBColor, duration=60000, steps=10) # Set our Blinkstick to morph from one color to another over the next ~55 seconds
    else:
      device['blink_device'].set_color(hex=RGBColor)

  if verbose:
    print("Device '{0}' set color to {1}".format(device['name'], visualColor))

  return True

def turn_off(device, dryrun, verbose):
  if not dryrun:
    device['blink_device'].turn_off()

  if verbose:
    print("Device '{0}' turned off".format(device['name']))

  return True

def set_color_from_schedule(configpath, dryrun, time, morph, ignorefailed, verbose):
  config = load_schedule(configpath)

  threads = []

  if not time:
    time = datetime.datetime.now()
  else:
    time = datetime.datetime.strptime(time, "%H:%M").time()

  if verbose:
    print("Processing for time: {}".format(time))

  time = time.hour*60 + time.minute
  entries = get_current_schedule_entries(config, time)

  for entry in entries:
    devices = []
    for device in config['devices']:
      if "all" in entry['devices'] or device['name'] in entry['devices']:
        if not dryrun:
          blinkDevice = blinkstick.find_by_serial(device['serial'])
          if blinkDevice is None:
            print("Couldn't find device '{0}' by serial number ({1})".format(device['name'], device['serial']))
            if not ignorefailed:
              sys.exit()
            else:
              continue
          if 'mode' in device:
            if device['mode'] in [0, 1]:
              if blinkDevice.get_mode() != device['mode']:
                blinkDevice.set_mode(int(device['mode']))
        else:
          blinkDevice = "dryrun socket"
        newDevice = dict(device)
        newDevice['blink_device'] = blinkDevice
        devices.append(newDevice)

    if "color" in entry:
      for device in devices:
        thread = Thread(target=set_color, args=(device, entry['color'], morph, dryrun, verbose))
        #thread.daemon = True # Python 2.7 compatible
        thread.start()
        threads.append(thread)
    elif "gradient" in entry:
      steps = (entry['end'] - entry['start'] + 1)
      position = (time - entry['start'])
      colorGradient = linear_gradient(entry['gradient']['start'], entry['gradient']['end'], steps)
      if 'type' in entry:
        if entry['type'] == 'natural':
          colorGradient = natural_gradient(entry['gradient']['start'], entry['gradient']['end'], steps)
      for device in devices:
        thread = Thread(target=set_color, args=(device, colorGradient[position], morph, dryrun, verbose))
        #thread.daemon = True # Python 2.7 compatible
        thread.start()
        threads.append(thread)
    elif "state" in entry:
      if not entry['state']: # on/yes/true in yaml are equivalent to a boolean True
        for device in devices:
          turn_off(device, dryrun, verbose)

  for thread in threads:
    thread.join()

def main():
  parser = argparse.ArgumentParser(description="Run a light schedule for one or more LED controllers. This is intended to run as often as you'd like via a cron job.")
  parser.add_argument("--config", "-c", help="Config file")
  parser.add_argument("--dry-run", "-d", help="Do a dry run, don't actually make the changes", action="store_true")
  parser.add_argument("--fudge-time", "-f", help="Fake the time with the provided value instead of using the actual time (HH:MM)")
  parser.add_argument("--ignore-failed", "-i", help="Ignore failed devices", action="store_true")
  parser.add_argument("--morph", "-m", help="Morph colors over the minute. Without this, the color is immediately set.", action="store_true")
  parser.add_argument("--verbose", "-v", help="Be more verbose", action="store_true")
  args = parser.parse_args()

  if args.config is None or not os.path.isfile(args.config):
    print("Config file doesn't exist or was not specified")
    return False

  schedule.every().minute.at(':00').do(set_color_from_schedule, args.config, args.dry_run, args.fudge_time, args.morph, args.ignore_failed, args.verbose)

  while True:
    schedule.run_pending()
    time.sleep(1)

if __name__=='__main__':
  sys.exit(main())
