#!/usr/bin/env python2

import argparse
import datetime
import re
import socket
import sys
import yaml

from colour import Color
from blinkstick import blinkstick

time_regex = re.compile("^[0-9]{1,2}:[0-9]{2}$")
timespan_regex = re.compile("^[0-9]{1,2}:[0-9]{2}-[0-9]{1,2}:[0-9]{2}$")

def loadschedule(configpath):
	configfile = open(configpath)
	data = yaml.safe_load(configfile)
	configfile.close()
	return data

def naturalgradient(start, end, steps):
	return list(Color(start).range_to(Color(end), steps))

def lineargradient(start, end, steps):
	'''returns a gradient list of (n) colors between
	  two hex colors. start_hex and finish_hex
	  should be the full six-digit color string,
	  inlcuding the number sign ("#FFFFFF")
	  Original from https://bsou.io/posts/color-gradients-with-python
	  Modified for my purposes'''

	start_hex = hextoRGB(Color(start).hex_l)
	end_hex = hextoRGB(Color(end).hex_l)

	# Initilize a list of the output colors with the starting color
	RGB_list = [RGBtohex(start_hex)]

	# Calcuate a color at each evenly spaced value of t from 1 to steps
	for step in range(1, steps):
		# Interpolate RGB vector for color at the current value of t
		curr_vector = [
			int(start_hex[j] + (float(step)/(steps-1))*(end_hex[j]-start_hex[j]))
			for j in range(3)
		]
		# Add it to our list of output colors
		RGB_list.append(RGBtohex(curr_vector))

	return RGB_list

def hextoRGB(hex):
	color = Color(hex)
	return (int(color.red * 255), int(color.green * 255), int(color.blue * 255))

def RGBtohex(rgb):
	color = Color(rgb=(rgb[0]/float(255), rgb[1]/float(255), rgb[2]/float(255)))
	return color.hex_l

def getcurrentscheduleentries(config, time):
	entries = []
	for entry in config['schedule']:
		if time_regex.match(entry['time']):
			split_entry_time = entry['time'].split(":")
			time_to_compare = int(split_entry_time[0])*60 + int(split_entry_time[1])
			if time == time_to_compare:
				entries.append(entry)

		if timespan_regex.match(entry['time']):
			split_entry_times = entry['time'].split("-")
			split_entry_time_start = split_entry_times[0].split(":")
			split_entry_time_end = split_entry_times[1].split(":")
			time_to_compare_start = int(split_entry_time_start[0])*60 + int(split_entry_time_start[1])
			time_to_compare_end = int(split_entry_time_end[0])*60 + int(split_entry_time_end[1])
			if time >= time_to_compare_start and time <= time_to_compare_end:
				new_entry = dict(entry)
				new_entry['start'] = time_to_compare_start
				new_entry['end'] = time_to_compare_end
				entries.append(new_entry)
	return entries

def setcolor(device, color, dryrun, verbose):
	if not isinstance(color, Color):
		color = Color(color)

	rgbcolor = color.hex_l
	if not dryrun:
		device['blink_device'].morph(hex=rgbcolor, duration=59000, steps=60) # Set our Blinkstick to morph from one step to another over the next 59 seconds

	if verbose:
		print("Device '{0}' set color to {1}".format(device['name'], rgbcolor))

	return True

def turnOff(device, dryrun, verbose):
	if not dryrun:
		device['blink_device'].turn_off()

	if verbose:
		print("Device '{0}' turned off".format(device['name']))

	return True

def setcolorfromschedule(configpath, dryrun, time, ignorefailed, verbose):
	config = loadschedule(configpath)

	if not time:
		time = datetime.datetime.now()
	else:
		time = datetime.datetime.strptime(time, "%H:%M").time()

	time = time.hour*60 + time.minute
	entries = getcurrentscheduleentries(config, time)

	for entry in entries:
		devices = []
		for device in config['devices']:
			if "all" in entry['devices'] or device['name'] in entry['devices']:
				if not dryrun:
					blink_device = blinkstick.find_by_serial(device['serial'])
					if blink_device is None:
						print("Couldn't find device '{0}' by serial number ({1})".format(device['name'], device['serial']))
						if not ignorefailed:
							sys.exit()
						else:
							continue
				else:
					blink_device = "dryrun socket"
				new_device = dict(device)
				new_device['blink_device'] = blink_device
				devices.append(new_device)

		if "color" in entry:
			for device in devices:
				setcolor(device, entry['color'], dryrun, verbose)
		elif "gradient" in entry:
			steps = (entry['end'] - entry['start'] + 1)
			position = (time - entry['start'])
			colorgradient = lineargradient(entry['gradient']['start'], entry['gradient']['end'], steps)
			if 'type' in entry:
				if entry['type'] == 'natural':
					colorgradient = naturalgradient(entry['gradient']['start'], entry['gradient']['end'], steps)
			for device in devices:
				setcolor(device, colorgradient[position], dryrun, verbose)
		elif "state" in entry:
			if not entry['state']: # on/yes/true in yaml are equivalent to a boolean True
				for device in devices:
					turnOff(device, dryrun, verify)

def main():
	parser = argparse.ArgumentParser(description="Run a light schedule for one or more LED controllers. This is intended to run as often as you'd like via a cron job.")
	parser.add_argument("--config", "-c", help="Config file")
	parser.add_argument("--dry-run", "-d", help="Do a dry run, don't actually make the changes", action='store_true')
	parser.add_argument("--fudge-time", "-f", help="Fake the time with the provided value instead of using the actual time (HH:MM)")
	parser.add_argument("--ignore-failed", "-i", help="Ignore failed devices", action="store_true")
	parser.add_argument("--verbose", "-v", help="Be more verbose", action="store_true")
	args = parser.parse_args()

	setcolorfromschedule(args.config, args.dry_run, args.fudge_time, args.ignore_failed, args.verbose)

if __name__=='__main__':
	sys.exit(main())
