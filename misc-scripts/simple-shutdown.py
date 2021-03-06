#!/usr/bin/env python

# 
# This file originates from Kite's AIO control board project.
# Author: Kite (Giles Burgess)
# 
# THIS HEADER MUST REMAIN WITH THIS FILE AT ALL TIMES
#
# This firmware is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This firmware is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this repo. If not, see <http://www.gnu.org/licenses/>.
#

import RPi.GPIO as GPIO 
import time
import math
import struct
import os,signal,sys
import subprocess
import re
import logging
import logging.handlers
try:
  from configparser import ConfigParser
except ImportError:
  from ConfigParser import ConfigParser  # ver. < 3.0

# Config variables
project_dir     = '/home/pi/ES-Simple-Scripts/'
bin_dir         = project_dir + 'misc-scripts/'
resources_dir   = project_dir + 'resources/'
ini_data_file   = bin_dir + 'osd/data.ini'
ini_config_file = bin_dir + 'osd/config.ini'
osd_path        = bin_dir + 'osd/saio-osd'

# Hardware variables
pi_shdn = 4
vpin    = 23
pi_vtx  = 1

# Anlog config values
vc = 2.0  # Switching voltage (v)     (leave this)
r = 31.0  # RC resistance     (k ohm) (adjust this!)
c = 1.0   # RC capacitance    (uF)    (leave this)

# Wifi variables
wifi_state = 'UNKNOWN'
wifi_off = 0
wifi_warning = 1
wifi_error = 2
wifi_1bar = 3
wifi_2bar = 4
wifi_3bar = 5

# Software variables
settings_shutdown = False #Enable ability to shut down system
settings_mode = 'ADVANCED' #ADVANCED=menu, NORMAL=ON/OFF only

# Read keyboard variables
infile_path = "/dev/input/event" + (sys.argv[1] if len(sys.argv) > 1 else "0")

FORMAT = 'llHHI'  # long int, long int, unsigned short, unsigned short, unsigned int
EVENT_SIZE = struct.calcsize(FORMAT)

key_volup = 103
key_voldown = 108
key_shutdown = 29
key_wifi_enable = 45
key_wifi_disable = 44
key_vtx_enable = 106
key_vtx_disable = 105

# Setup
logging.basicConfig(level=logging.DEBUG)
logging.info("Program Started")

# Init GPIO pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pi_shdn, GPIO.IN)

if settings_mode == 'ADVANCED':
  # Set up configOSD file
  configOSD = ConfigParser()
  configOSD.add_section('protocol')
  configOSD.set('protocol', 'version', 1)
  configOSD.add_section('data')
  configOSD.set('data', 'voltage', '-.--')
  configOSD.set('data', 'temperature', '--.-')
  configOSD.set('data', 'showdebug', 1)
  configOSD.set('data', 'showwifi', 0)
  configOSD.set('data', 'showmute', 0)

  try:
    with open(ini_data_file, 'w') as configfile:
      configOSD.write(configfile)
  except Expection as e:
    logging.exception("ERROR: Failed to create configOSD file");
    sys.exit(1);
      
  # Set up OSD service
  try:
    osd_proc = subprocess.Popen([osd_path, "-d", ini_data_file, "-c", ini_config_file])
    time.sleep(1)
    osd_poll = osd_proc.poll()
    if (osd_poll):
      logging.error("ERROR: Failed to start OSD, got return code [" + str(osd_poll) + "]\n")
      sys.exit(1)
  except Exception as e:
    logging.exception("ERROR: Failed start OSD binary");
    sys.exit(1);

# Check for advanced mode state
def checkAdvanced():
  state = not GPIO.input(pi_shdn)
  if (state):
    doPngOverlay(resources_dir + 'menu_items.png')
    looping = True
    reset = False
    while looping:
      key = readKeyPresses()
      
      if (key == key_shutdown):
        logging.info("SHUTDOWN KEY")
        doPngOverlay(resources_dir + 'shutting_down.png')
        doShutdown()
      elif (key == key_volup):
        logging.info("VOLUP KEY")
        doPngOverlay(resources_dir + 'vol_up.png')
        doVol('UP')
        time.sleep(0.5)
        reset = True
      elif (key == key_voldown):
        logging.info("VOLDOWN KEY")
        doPngOverlay(resources_dir + 'vol_down.png')
        doVol('DOWN')
        time.sleep(0.5)
        reset = True
      elif (key == key_wifi_enable):
        logging.info("WIFI ENABLE KEY")
        doPngOverlay(resources_dir + 'wifi_enable.png')
        doWifi('ON')
        time.sleep(1)
        reset = True
      elif (key == key_wifi_disable):
        logging.info("WIFI DISABLE KEY")
        doPngOverlay(resources_dir + 'wifi_disable.png')
        doWifi('OFF')
        time.sleep(1)
        reset = True
      elif (key == key_vtx_enable):
        logging.info("VTX ENABLE KEY")
        doPngOverlay(resources_dir + 'vtx_enable.png')
        doVtx('ON')
        time.sleep(1)
        reset = True
      elif (key == key_vtx_disable):
        logging.info("VTX DISABLE KEY")
        doPngOverlay(resources_dir + 'vtx_disable.png')
        doVtx('OFF')
        time.sleep(1)
        reset = True
      else:
        logging.info("UNKNOWN KEY")
      
      if GPIO.input(pi_shdn):
        doPngOverlay(False)
        looping = False
      
      if reset:
        doPngOverlay(resources_dir + 'menu_items.png')
        reset = False
      
      time.sleep(0.2)

# Read the keyboard for press (1 sec)
def readKeyPresses():
  ret = 0
  try:
    # Open file in binary mode
    in_file = open(infile_path, "rb")

    event = 0
    with Timeout(1):
      event = in_file.read(EVENT_SIZE)

    (tv_sec, tv_usec, type, code, value) = struct.unpack(FORMAT, event)

    if type != 0 or code != 0 or value != 0:
      print("Event type %u, code %u, value %u at %d.%d" % (type, code, value, tv_sec, tv_usec))
      ret = code
    else:
      # Events with code, type and value == 0 are "separator" events
      print("===========================================")

    #event = in_file.read(EVENT_SIZE)

    in_file.close()
  except:
    logging.error("Failed to read keypresses")
    pass
  
  return ret

# Check for shutdown state
def checkShdn():
  state = not GPIO.input(pi_shdn)
  if (state):
    logging.info("SHUTDOWN")
    doShutdown()

# Class used to timeout commands
class Timeout():
  """Timeout class using ALARM signal."""
  class Timeout(Exception):
    pass

  def __init__(self, sec):
    self.sec = sec

  def __enter__(self):
    signal.signal(signal.SIGALRM, self.raise_timeout)
    signal.alarm(self.sec)

  def __exit__(self, *args):
    signal.alarm(0)    # disable alarm

  def raise_timeout(self, *args):
    raise Timeout.Timeout()

# READ ANALOG
def analog_read_start(pin):
  GPIO.setup(pin, GPIO.OUT)
  GPIO.output(pin, GPIO.LOW)
  time.sleep(0.1)

  analog_start_time = time.time()
  GPIO.setup(pin, GPIO.IN)
  res = GPIO.wait_for_edge(pin, GPIO.RISING, timeout=200)
  analog_end_time = time.time()
  GPIO.setup(pin, GPIO.OUT)
  GPIO.output(pin, GPIO.LOW)

  voltage = - ( vc / (math.exp(-((analog_end_time - analog_start_time)*1000)/(r*c))-1) )

  if res is None:
    return False
  else:
    return voltage

# Read CPU temp
def getCPUtemperature():
  res = os.popen('vcgencmd measure_temp').readline()
  return float(res.replace("temp=","").replace("'C\n",""))

# Create ini configOSD
def createINI(volt, curr, temp, debug, wifi, mute, file):
  #configOSD.set('data', 'voltage', '{0:.2f}'.format(volt/100.00))
  configOSD.set('data', 'voltage', volt)
  configOSD.set('data', 'temperature', temp)
  configOSD.set('data', 'showdebug', debug)
  configOSD.set('data', 'showwifi', wifi)
  configOSD.set('data', 'showmute', mute)

  with open(file, 'w') as configfile:
    configOSD.write(configfile)
  
  osd_proc.send_signal(signal.SIGUSR1)

# Do a shutdown
def doShutdown():
  os.system("sudo shutdown -h now")
  try:
    sys.stdout.close()
  except:
    pass
  try:
    sys.stderr.close()
  except:
    pass
  sys.exit(0)

# Set volume
def doVol(state):
  if state == 'UP':
    os.system('sudo amixer -M set PCM 20%+')
  elif state == 'DOWN':
    os.system('sudo amixer -M set PCM 20%-')
  else:
    logger.info("Unknown volume")

# Set VTX
def doVtx(state):
  if state == 'ON':
    GPIO.setup(pi_vtx, GPIO.OUT)
    GPIO.output(pi_vtx, GPIO.LOW)
  elif state == 'OFF':
    GPIO.setup(pi_vtx, GPIO.OUT)
    GPIO.output(pi_vtx, GPIO.HIGH)
    GPIO.setup(pi_vtx, GPIO.IN)
  else:
    logger.info("Unknown vtx")

# Set wifi
def doWifi(state):
  if state == 'ON':
    os.system("sudo rfkill unblock wifi")
    os.system("sudo rfkill unblock bluetooth")
  elif state == 'OFF':
    os.system("sudo rfkill block wifi")
    os.system("sudo rfkill block bluetooth")
  else:
    logger.info("Unknown wifi")

# Show MP4 overlay
def doVidOverlay(overlay):
  os.system("/usr/bin/omxplayer --no-osd --layer 999999 " + overlay + " --alpha 160;");

# Show PNG overlay
def doPngOverlay(overlay):
  try:
    os.system('kill -9 `pidof pngview`');
  except:
    pass
  if overlay:
    try:
      os.system(bin_dir + "pngview -b 0 -l 999999 " + overlay + "&");
    except:
      pass

# Misc functions
def clamp(n, minn, maxn):
  return max(min(maxn, n), minn)

# Main loop
try:
  print "STARTED!"
  analog_read_start(vpin) # perform analog read to clear delays/etc
  
  while 1:
    
    if settings_mode == 'NORMAL':
      if (settings_shutdown):
        checkShdn()
    
    elif settings_mode == 'ADVANCED':
      checkAdvanced()
      
      volt = '{0:.0f}'.format(analog_read_start(vpin)*100.00)
      temp = getCPUtemperature()
      createINI(volt, 0, temp, 0, 0, 0, ini_data_file)
    
    else:
      logging.info("ERROR: settings_mode incorrectly defined")
      sys.exit(1)
    
    time.sleep(4);
  
except KeyboardInterrupt:
  GPIO.cleanup
  osd_proc.terminate()
