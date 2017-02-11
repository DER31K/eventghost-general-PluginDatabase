# -*- coding: utf-8 -*-
#
# This file is a plugin for EventGhost.
# Copyright (C) 2005-2009 Lars-Peter Voss <bitmonster@eventghost.org>
#
# EventGhost is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by the
# Free Software Foundation;
#
# EventGhost is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

r"""<rst>
Plugin for the `ATI Remote Wonder II`__ remote.

|

.. image:: picture.jpg
   :align: center

__ http://ati.amd.com/products/remotewonder2/index.html
"""


import eg

eg.RegisterPlugin(
	name="ATI Remote Wonder II (WinUSB)",
	description=__doc__,
	url="http://www.eventghost.net/forum/viewtopic.php?t=915",
	author="Bitmonster",
	version="1.0.2",
	kind="remote",
	hardwareId = "USB\\VID_0471&PID_0602",
	guid="{74DBFE39-FEF6-41E5-A047-96454512B58D}",
)

from math import atan2, pi
from eg.WinApi.Dynamic import mouse_event
from threading import Timer
	

CODES = {
	0: "Num0",
	1: "Num1",
	2: "Num2",
	3: "Num3",
	4: "Num4",
	5: "Num5",
	6: "Num6",
	7: "Num7",
	8: "Num8",
	9: "Num9",
	12: "Power",
	13: "Mute",
	16: "VolumeUp",
	17: "VolumeDown",
	32: "ChannelUp",
	33: "ChannelDown",
	40: "FastForward",
	41: "FastRewind",
	44: "Play",
	48: "Pause",
	49: "Stop",
	55: "Record",
	56: "DVD",
	57: "TV",
	84: "Setup",
	88: "Up",
	89: "Down",
	90: "Left",
	91: "Right",
	92: "Ok",
	120: "A",
	121: "B",
	122: "C",
	123: "D",
	124: "E",
	125: "F",
	130: "Checkmark",
	142: "ATI",
	150: "Stopwatch",
	190: "Help",
	208: "Hand",
	213: "Resize",
	249: "Info",
}

DEVICES = {
	0: "AUX1",
	1: "AUX2",
	2: "AUX3",
	3: "AUX4",
	4: "PC",
}

class MyTimer():

	def __init__(self, time, callback):
		self.timer = Timer(time, callback)

	def Start(self):
		self.Close()
		self.timer.start()

	def Close(self):
		try: self.timer.close()
		except: pass


class AtiRemoteWonder2(eg.PluginBase):

	def __start__(self, mousemaxspeed=10, mouseacceleration=1, debugging=False, mousereset=False, mousetimeout=0.25, mouseresolution=1.0):

		if debugging:
			eg.PrintNotice('AtiRemoteWonder2: Debugging Active')

		self.mousemaxspeed = float(mousemaxspeed) / mouseresolution
		self.mouseacceleration = float(mouseacceleration) / mouseresolution
		self.debugging = debugging
		self.mousereset = mousereset
		self.speed = mousemaxspeed
		self.accel = mouseacceleration
		self.buttoncount = 0
		self.mousecounter = 0
		self.winUsb = eg.WinUsb(self)
		self.winUsb.Device(self.Callback1, 3).AddHardwareId(
			"ATI Remote Wonder II (Mouse)", "USB\\VID_0471&PID_0602&MI_00"
		)
		self.winUsb.Device(self.Callback2, 3).AddHardwareId(
			"ATI Remote Wonder II (Buttons)", "USB\\VID_0471&PID_0602&MI_01"
		)
		self.winUsb.Start()
		self.lastDirection = None
		self.currentDevice = None
		self.timer = eg.ResettableTimer(self.OnTimeOut)
		self.receiveQueue = eg.plugins.Mouse.plugin.thread.receiveQueue

		self.Timer = MyTimer(mousetimeout, self.ResetMouse)

	def __stop__(self):
		self.Timer.Close()
		self.winUsb.Stop()
		self.timer.Stop()


	def Callback1(self, (device, x, y)):
		logging = (hex(device), hex(x), hex(y))
		if x > 127: x -= 256
		if y > 127: y -= 256
		degree = (round((atan2(x, -y) / pi) * 180)) % 360

		if self.debugging:
			res = (
				'hex values: '+str(logging)[1:-1],
				'direction: '+str(dict(x=x, y=y, angle=degree))[1:-1],
				'mouse code count: '+str(self.mousecounter),
				'speed: '+str(self.speed),
				'accel: '+str(self.accel)
				)
			print res

		self.mousecounter += 1
		if degree != self.lastDirection:
			if self.mousereset:
				self.speed = self.mousemaxspeed
				self.accel = self.mouseacceleration
			self.mousecounter = 0
			self.lastDirection = degree

		if self.mousecounter == 3:
			self.mousecounter = 0
			self.receiveQueue.put((degree, 3, self.speed, self.accel, 0))
			if self.speed < 60: self.speed += 0.25
			if self.accel < 30: self.accel += 0.10

		self.Timer.Start()
		self.timer.Reset(100)

	def Callback2(self, (device, event, code)):
		self.buttoncount += 1
		if self.debugging:
			res = (
				'hex values: '+str((hex(device), hex(event), hex(code)))[1:-1],
				'event: '+DEVICES[device],
				'button code count: '+str(self.buttoncount)
				)
			print res

		if device != self.currentDevice:
			self.buttoncount = 0
			self.currentDevice = device
			self.TriggerEvent(DEVICES[device])
		if event == 1:
			if code == 169:
				mouse_event(0x0002, 0, 0, 0, 0)
			elif code == 170:
				mouse_event(0x0008, 0, 0, 0, 0)
			elif code != 63:
				self.TriggerEnduringEvent(CODES.get(code, "%i" % code))
		elif event == 0:
			if code == 169:
				mouse_event(0x0004, 0, 0, 0, 0)
			elif code == 170:
				mouse_event(0x0010, 0, 0, 0, 0)
			else:
				self.EndLastEvent()

	@eg.LogIt
	def OnTimeOut(self):
		self.receiveQueue.put((-2,))
		self.lastDirection = None

	def ResetMouse(self):
		self.speed = self.mousemaxspeed
		self.accel = self.mouseacceleration
		self.mousecounter = 0

	def Configure(self,
				  mousemaxspeed=10,
				  mouseacceleration=1,
				  debugging=False,
				  mousereset=True,
				  mousetimeout=0.25,
				  mouseresolution=1.0
				  ):

		panel = eg.ConfigPanel()

		resetCtrl = panel.CheckBox(mousereset)
		timerCtrl = panel.SpinNumCtrl(mousetimeout, min=0.0, max=120.0, increment=0.1)
		speedCtrl = panel.SpinIntCtrl(mousemaxspeed)
		accelCtrl = panel.SpinIntCtrl(mouseacceleration)
		resolCtrl = panel.SpinNumCtrl(float(mouseresolution), min=1.0, max=5.0, increment=0.25)
		debugCtrl = panel.CheckBox(debugging)

		panel.AddLine('Mouse Speed:', speedCtrl)
		panel.AddLine('Mouse Acceleration:', accelCtrl)
		panel.AddLine('Unchecking this next option will keep the current speed\n'
					  'and acceleration if you change the direction of the mouse.'
					  )
		panel.AddLine('Reset on Direction Change:', resetCtrl)
		panel.AddLine('This is the amount of time it will take before the speed\n'
					  'and acceleration reset back to their base values.'
					  )
		panel.AddLine('Reset Time:', timerCtrl, 'seconds')
		panel.AddLine('By changing this next factor controls the amount of resolution\n'
					  'you will have on the speed and acceleration.'
					  )
		panel.AddLine('Resolution Factor:', resolCtrl)

		panel.AddLine('Show Incoming Data:', debugCtrl)

		while panel.Affirmed():
			panel.SetResult(
				speedCtrl.GetValue(),
				accelCtrl.GetValue(),
				debugCtrl.GetValue(),
				resetCtrl.GetValue(),
				timerCtrl.GetValue(),
				resolCtrl.GetValue()
				)