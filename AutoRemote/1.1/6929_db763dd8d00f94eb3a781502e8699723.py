# -*- coding: utf-8 -*-


import eg

eg.RegisterPlugin(
    name = "AutoRemote",
    author = "joaomgcd",
    version = "1.1",
    guid = "{C18A174E-71E3-4C74-9A2B-8653CE9991E1}",
    description = (
        "Send and receive messages to and from AutoRemote on Android."
    ),
    canMultiLoad = True,
    icon = (
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAB3RJTUUH3AgXChElQdwgkgAAA2NJREFUOMuFkktsVGUYht9zm3Pm2pkOzPQylKGFTsWCNCrBUCuYtEhjrVQ04oY00WjcuSExISEKJizcGOKaeKlau6jBpAEheCm9oNQ2LdbpWNopQy8znUudc5n/nDnn/C5MSVnx7Z/nTd73Y/CYuzg+CZgmt564R6WaWubCsVarvfdCJJ7M9D4ZEr/kHyewJY/AWNY5YVs4UZbc0Q9/ntXdseZn6w/t7Vamf2EYALj52y282Nb6CHjt1xEce+EweoqUb8nLqeL6xlqR8kE1b/B6kcxWmWrqCT85z2wClFLcnpqpUxXVo+Syie5Xu8zRiclWT2Uw00+kd6cX1RPbYed11azJZWSDplNnr3184mtuUxBrfnpnciVzKV2QT9ngbg4OfGP8eH1kaD2TOyK5g/0JTeow/lVlLVtaVu4vO4r3k/Hw7tY7DzugHGvplrWtbOI5j8c50H/llmmYbKNByo2t09/e9dqS67PcYWcpueSSSH6OKhsLllak/NjY+A5eEusfZOQGr8UdpGAgOvgW2ynCtbSGyql+qmjZk02nz3/RwSkTN+4VatOpB20BobTHJfIM89XAlcHVvPKKz+uzwDFCVTiECiKDzAxilz4Jj9+PO0I7XfU2MLKs3Ihsr3jnrZ5LqX0v7WdcDpj86npBkInFuj0VrBcGaue+RzX3D8JtzZBnAxh19iDPR5lCdg12SYUg+CgwZM1cHQIAsGfeP/1yY/2Oy5wggJNzqJDnEdxdB1vfAFlRwaXmoZY1RAKe4bMfvN3+elfn0uXvBh/Ozf9w9XrDhma5wXBAaQOWJoPRCTiXD5peABvbA6pZ0B28c/jPeGR5cW71zde6rU0Bm0ytfF6UtTcI0eELB2gwVgdZNrGWAZTYSawbTvA8D4WQZ6Zn5/sUQuq2PhyvaiRtEboQY/JGZbyvKe6W6IJrH0P8UdDKKC2zNlyClcrn5WUNkA/s3VV+RLAzEj7j11Z6henhcznf/lIq3OIk3mqwLAvWKjNOgSOhgKezkE2rokPkOo8+v7xVwABAZuqnpsTCyntjWfGUCTYUjVR95PeIZHzir08Eh2g/1Vh7pKv96Mgm9PvdBA42N/7fweLffyB0oCO+SIOf6oY+KjL2mAPlvuNthy46WDrjYO3JmupwemvqJgwA/wFagpdq+6hoCwAAAABJRU5ErkJggg=="
    ),
)

import wx
import os
import sys
import posixpath
import base64
import time
import urllib2
import socket
import httplib
from threading import Thread, Event
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
from urllib import unquote, unquote_plus
from os.path import getmtime
import json
import jinja2
import cStringIO
import re

class FileLoader(jinja2.BaseLoader):
    """Loads templates from the file system."""

    def get_source(self, environment, filename):
        try:
            sourceFile = open(filename, "rb")
        except IOError:
            raise jinja2.TemplateNotFound(filename)
        try:
            contents = sourceFile.read().decode("utf-8")
        finally:
            sourceFile.close()

        mtime = getmtime(filename)
        def uptodate():
            try:
                return getmtime(filename) == mtime
            except OSError:
                return False
        return contents, filename, uptodate



class MyServer(ThreadingMixIn, HTTPServer):
    address_family = getattr(socket, 'AF_INET6', None)

    def __init__(self, requestHandler, port):
        self.httpdThread = None
        self.abort = False
        for res in socket.getaddrinfo(None, port, socket.AF_UNSPEC,
                              socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
            #print res
            self.address_family = res[0]
            self.socket_type = res[1]
            address = res[4]
            break

        HTTPServer.__init__(self, address, requestHandler)


    def server_bind(self):
        """Called by constructor to bind the socket."""
        if socket.has_ipv6 and sys.getwindowsversion()[0] > 5:
            # make it a dual-stack socket if OS is Vista/Win7
            IPPROTO_IPV6 = 41
            self.socket.setsockopt(IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        HTTPServer.server_bind(self)


    def Start(self):
        """Starts the HTTP server thread"""
        self.httpdThread = Thread(name="WebserverThread", target=self.Run)
        self.httpdThread.start()


    def Run(self):
        try:
            # Handle one request at a time until stopped
            while not self.abort:
                self.handle_request()
        finally:
            self.httpdThread = None


    def Stop(self):
        """Stops the HTTP server thread"""
        if self.httpdThread:
            self.abort = True
            # closing the socket will awake the underlying select.select() call
            # so the handle_request() loop will notice the abort flag
            # immediately
            self.socket.close()
            self.RequestHandlerClass.repeatTimer.Stop()

    #def handle_error(self, request, client_address):
    #    eg.PrintError("HTTP Error")


class AutoRemotePayload:
	def __init__(self, params, commands):
	        self.arpar = params
	        self.arcomm = commands
	def __str__(self):
		return "params: " + self.arpar + "; command(s): " + self.arcomm + ";"
	
class MyHTTPRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = SimpleHTTPRequestHandler.extensions_map.copy()
    extensions_map['.ico'] = 'image/x-icon'
    extensions_map['.manifest'] = 'text/cache-manifest'
    # these class attributes will be set by the plugin
    authString = None
    authRealm = None
    basepath = None
    repeatTimer = None
    environment = None
    plugin = None

    def version_string(self):
        """Return the server software version string."""
        return "EventGhost/" + eg.Version.string


    def Authenticate(self):
        # only authenticate, if set
        if self.authString is None:
            return True

        # do Basic HTTP-Authentication
        authHeader = self.headers.get('authorization')
        if authHeader is not None:
            authType, authString = authHeader.split(' ', 2)
            if authType.lower() == 'basic' and authString == self.authString:
                return True

        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="%s"' % self.authRealm)
        return False


    def SendContent(self, path):       
        self.send_response(200)
        self.send_header("Content-type", 'text/html')
        self.send_header("Content-Length", len("OK"))
        self.end_headers()
        self.wfile.write("OK".encode("UTF-8"))
        self.wfile.close()


    def do_POST(self):
        """Serve a POST request."""
        # First do Basic HTTP-Authentication, if set
        #print "do post"
        #print self.headers
        contentLength = int(self.headers.get('content-length'))
        content = self.rfile.read(contentLength)
        #print content
        if not self.Authenticate():
            return

        try:
            data = json.loads(content)
        except:
            eg.PrintTraceback()
        print data
        methodName = data["method"]
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        result = None
        if methodName == "TriggerEvent":
            self.plugin.TriggerEvent(*args, **kwargs)
        elif methodName == "TriggerEnduringEvent":
            self.plugin.TriggerEnduringEvent(*args, **kwargs)
            self.repeatTimer.Reset(2000)
        elif methodName == "RepeatEnduringEvent":
            self.repeatTimer.Reset(2000)
        elif methodName == "EndLastEvent":
            self.repeatTimer.Reset(None)
            self.plugin.EndLastEvent()
        content = json.dumps(result)
        self.send_response(200)
        self.send_header("Content-type", 'application/json; charset=UTF-8')
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content.encode("UTF-8"))
        self.wfile.close()


    def do_GET(self):
        """Serve a GET request."""
        # First do Basic HTTP-Authentication, if set
        if not self.Authenticate():
            return

        path, dummy, remaining = self.path.partition("?")
        if remaining:
            if "message=" in remaining:
            	    message = remaining.split("message=")[1]
            	    message = unquote_plus(message).decode("utf-8")
            	    message, andSign, rest = message.partition("&")
		    queries = remaining.split("#", 1)[0].split("&")
		    queries = [unquote_plus(part).decode("latin1") for part in queries]
		    if len(queries) > 0:
			event = "Message"        	

			if "withoutRelease" in queries:
			    queries.remove("withoutRelease")
			    event = self.plugin.TriggerEnduringEvent(event, queries)
			    while not event.isEnded:
				time.sleep(0.05)
			elif event == "ButtonReleased":
			    self.plugin.EndLastEvent()
			else:
			    params, seperator, commands = message.partition("=:=")
			    params = params.split(" ")
			    if "=:=" in commands:
			    	commands = commands.split("=:=")
			    payload = AutoRemotePayload(params, commands)
			    event = event + "." + params[0]
			    event = self.plugin.TriggerEvent(event, payload)
			    while not event.isEnded:
				time.sleep(0.05)
        try:
            self.SendContent(path)
        except Exception, exc:
            self.plugin.EndLastEvent()
            eg.PrintError("Webserver error", self.path)
            eg.PrintError("Exception", unicode(exc))
            if exc.args[0] == 10053: # Software caused connection abort
                pass
            elif exc.args[0] == 10054: # Connection reset by peer
                pass
            else:
                raise


    def log_message(self, format, *args):
        # suppress all messages
        pass


    def copyfile(self, src, dst):
        dst.write(src.read())


    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        # stolen from SimpleHTTPServer.SimpleHTTPRequestHandler
        # but changed to handle files from a defined basepath instead
        # of os.getcwd()
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = posixpath.normpath(unquote(path))
        words = [word for word in path.split('/') if word]
        path = self.basepath
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir):
                continue
            path = os.path.join(path, word)
        return path



class SendMessage(eg.ActionBase):
    name = "Send Message"
    description = "Send a message to your Android device"
    def __call__(self,  name="", url="", key="", message="", ttl="", password="", target="", channel=""):
    	
    	p = re.compile('\{[^\}]+\}')
	list = p.findall(message)
	toEval = [item.replace('{','').replace('}','') for item in list ]
	try:
		for item in toEval:
			message = message.replace('{' + item + '}', eval(item))
		print "Sending " + message
		message = message.encode('utf-8')
		url = 'http://autoremotejoaomgcd.appspot.com/sendmessage?message={0}&target={1}&ttl={2}&password={3}&key={4}&sender={5}'.format(message, target, ttl, password, key, self.plugin.name)
		print url
	        import urllib; urllib.urlopen(url)
	except TypeError:
		print "Error: {" + item + '} does not evaluate to a String. Not sending message.'

    def GetLabel(self,  name="", url="", key="",  message="", ttl="", password="", target="", channel=""):
    	return "Sending " + message + " to " + name
    	
    def Configure(self,  name="", url="", key="",  message="", ttl="", password="", target="", channel=""):
        panel = eg.ConfigPanel(self)      
        
	self.devicesCtrl = panel.Choice(0, [])
        panel.sizer.Add(panel.StaticText("Device:"), 1, wx.EXPAND)
        panel.sizer.Add(self.devicesCtrl, 1, wx.EXPAND)
	for device in self.plugin.devices:
		self.devicesCtrl.Append(device.name)
	
	self.devicesCtrl.SetStringSelection(name)
        
        messageCtrl = panel.TextCtrl(message)
        panel.sizer.Add(panel.StaticText("Message:"), 1, wx.EXPAND)
        panel.sizer.Add(messageCtrl, 1, wx.EXPAND)        
        
        ttlCtrl = panel.TextCtrl(ttl)
        panel.sizer.Add(panel.StaticText("Time To Live:"), 1, wx.EXPAND)
        panel.sizer.Add(ttlCtrl, 1, wx.EXPAND)        
        
        targetCtrl = panel.TextCtrl(target)
        panel.sizer.Add(panel.StaticText("Target:"), 1, wx.EXPAND)
        panel.sizer.Add(targetCtrl, 1, wx.EXPAND)        
        
        passwordCtrl = panel.TextCtrl(password)
        panel.sizer.Add(panel.StaticText("Password:"), 1, wx.EXPAND)
        panel.sizer.Add(passwordCtrl, 1, wx.EXPAND)
      
        channelCtrl = panel.TextCtrl(channel)
        panel.sizer.Add(panel.StaticText("Channel:"), 1, wx.EXPAND)
        panel.sizer.Add(channelCtrl, 1, wx.EXPAND)
        
        while panel.Affirmed():
            selectedDevice = self.GetSelectedDevice()
            
            panel.SetResult(
                selectedDevice.name,
                selectedDevice.url,
                selectedDevice.key,
                messageCtrl.GetValue(),
                ttlCtrl.GetValue(),
                passwordCtrl.GetValue(),
                targetCtrl.GetValue(),
                channelCtrl.GetValue(),
            )
	
	
    def GetSelectedDevice(self):
    	for device in self.plugin.devices:
    		if device.name == self.devicesCtrl.GetStringSelection():
    			return device
    	
class RegisterEventGhost(eg.ActionBase):
    name = "Register EventGhost"  
    description = "Register or refresh EventGhost info on your Android device. Recommended use is at user login and on EventGhost startup."

    def __call__(self,  name="", url="",key="", defaultchannel=""):
    	
    	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    	s.connect(("gmail.com",80))
    	localip = s.getsockname()[0]
    	port = str(self.plugin.port)
        publicIp = self.plugin.publicIp
    	print(localip + ":" + port)
    	import urllib; urllib.urlopen('http://autoremotejoaomgcd.appspot.com/registerpc?id={0}&name={0}&localip={1}:{2}&publicip={5}:{2}&channel={3}&key={4}'.format(self.plugin.name, localip, port, defaultchannel, key, publicIp))


    def GetLabel(self,  name="", url="",key="", defaultchannel=""):
    	return "Registering on " + name
    	
    def Configure(self,  name="", url="", key="", defaultchannel=""):
        panel = eg.ConfigPanel(self)
        
	self.devicesCtrl = panel.Choice(0, [])
	panel.sizer.Add(panel.StaticText("Device:"), 1, wx.EXPAND)
	panel.sizer.Add(self.devicesCtrl, 1, wx.EXPAND)
	for device in self.plugin.devices:
		self.devicesCtrl.Append(device.name)
		
	self.devicesCtrl.SetStringSelection(name)
        
        channelCtrl = panel.TextCtrl(defaultchannel)
        panel.sizer.Add(panel.StaticText("Default channel (optional):"), 1, wx.EXPAND)
        panel.sizer.Add(channelCtrl, 1, wx.EXPAND)       
        
        
        while panel.Affirmed():
            selectedDevice = self.GetSelectedDevice()
            panel.SetResult(
                selectedDevice.name,
                selectedDevice.url,
                selectedDevice.key,
                channelCtrl.GetValue(),
            )

    
    def GetSelectedDevice(self):
	for device in self.plugin.devices:
		if device.name == self.devicesCtrl.GetStringSelection():
			return device
    	
class SendNotification(eg.ActionBase):
    name = "Send Notification"  
    description = "Send a notification"

    def __call__(self, key="",  name="", title="", text="", url="", channel="", message="", id="", action="", icon="", led_color="", led_on="", led_off="", picture="", action_share="", action_button1="", action_label1="", action_button2="", action_label2="", action_button3="", action_label3="", sound=""):

        title = title.encode('utf-8')
        text = text.encode('utf-8')
        url = url.encode('utf-8')
        channel = channel.encode('utf-8')
        message = message.encode('utf-8')
        id = id.encode('utf-8')
        action = action.encode('utf-8')
        icon = icon.encode('utf-8')
        led_color = led_color.encode('utf-8')
        led_on = led_on.encode('utf-8')
        led_off = led_off.encode('utf-8')
        picture = picture.encode('utf-8')
        action_share = action_share.encode('utf-8')
        action_button1 = action_button1.encode('utf-8')
        action_label1 = action_label1.encode('utf-8')
        action_button2 = action_button2.encode('utf-8')
        action_label2 = action_label2.encode('utf-8')
        action_button3 = action_button3.encode('utf-8')
        action_label3 = action_label3.encode('utf-8')
        sound = sound.encode('utf-8')

        import urllib
        f = { 'title' : title, 'text' : text, 'url': url, 'channel': channel, 'message': message, 'id': id, 'action': action, 'icon': icon, 'led': led_color, 'ledon': led_on, 'ledoff': led_off, 'picture': picture, 'share': action_share, 'actionbutton1': action_button1, 'actionlabel1': action_label1, 'actionbutton2': action_button2, 'actionlabel2': action_label2, 'actionbutton3': action_button3, 'actionlabel3':action_label3, 'key': key, 'sound': sound}
        
        urllib.urlopen('http://autoremotejoaomgcd.appspot.com/sendnotification?' + urllib.urlencode(f))


    def GetLabel(self, key="",  name="",title="", text="",  url="", channel="", message="", id="", action="", icon="", led_color="", led_on="", led_off="", picture="", action_share="", action_button1="", action_label1="", action_button2="", action_label2="", action_button3="", action_label3="", sound=""):
        return "Sending Notification"
        
    def Configure(self, key="",  name="",title="", text="",  url="",  channel="", message="", id="", action="", icon="", led_color="", led_on="", led_off="", picture="", action_share="", action_button1="", action_label1="", action_button2="", action_label2="", action_button3="", action_label3="", sound=""):
        panel = eg.ConfigPanel(self)
        
        self.devicesCtrl = panel.Choice(0, [])
        for device in self.plugin.devices:
            self.devicesCtrl.Append(device.name)
            
        self.devicesCtrl.SetStringSelection(name)
        panel.AddLine("Device:", self.devicesCtrl)

        titleCtrl = panel.TextCtrl(title)
        panel.AddLine("Title:", titleCtrl)

        textCtrl = panel.TextCtrl(text)
        panel.AddLine("Text:", textCtrl)

        messageCtrl = panel.TextCtrl(message)
        panel.AddLine("Automatic Action:", messageCtrl)

        channelCtrl = panel.TextCtrl(channel)
        panel.AddLine("Channel:", channelCtrl)

        urlCtrl = panel.TextCtrl(url)
        panel.AddLine("Url on Touch:", urlCtrl)

        idCtrl = panel.TextCtrl(id)
        panel.AddLine("Id (same id will overlap):", idCtrl)

        soundCtrl = panel.TextCtrl(sound)
        panel.AddLine("Sound (1 to 10):", soundCtrl)

        actionCtrl = panel.TextCtrl(action)
        panel.AddLine("Action on Touch:", actionCtrl)

        iconCtrl = panel.TextCtrl(icon)
        panel.AddLine("Icon Url:", iconCtrl)

        led_colorCtrl = panel.Choice(0, ['red', 'blue', 'green', 'black', 'white', 'gray', 'cyan', 'magenta', 'yellow', 'lightgray', 'darkgray'])
        panel.AddLine("Led Color:", led_colorCtrl)

        led_onCtrl = panel.TextCtrl(led_on)
        panel.AddLine("Led On Time:", led_onCtrl)

        led_offCtrl = panel.TextCtrl(led_off)
        panel.AddLine("Led Off Time:", led_offCtrl)

        pictureCtrl = panel.TextCtrl(picture)
        panel.AddLine("Picture Url:", pictureCtrl)

        action_shareCtrl = panel.TextCtrl(action_share)
        panel.AddLine("Show Share:", action_shareCtrl)

        action_button1Ctrl = panel.TextCtrl(action_button1)
        panel.AddLine("Action 1:", action_button1Ctrl)

        action_label1Ctrl = panel.TextCtrl(action_label1)
        panel.AddLine("Action 1 Label:", action_label1Ctrl)

        action_button2Ctrl = panel.TextCtrl(action_button2)
        panel.AddLine("Action 2:", action_button2Ctrl)

        action_label2Ctrl = panel.TextCtrl(action_label2)
        panel.AddLine("Action 2 Label:", action_label2Ctrl)

        action_button3Ctrl = panel.TextCtrl(action_button3)
        panel.AddLine("Action 3:", action_button3Ctrl)

        action_label3Ctrl = panel.TextCtrl(action_label3)
        panel.AddLine("Action 3 Label:", action_label3Ctrl)

        
        while panel.Affirmed():
            selectedDevice = self.GetSelectedDevice()
            panel.SetResult(
                selectedDevice.key,
                selectedDevice.name,
                titleCtrl.GetValue(),
                textCtrl.GetValue(),
                urlCtrl.GetValue(),
                channelCtrl.GetValue(),
                messageCtrl.GetValue(),
                idCtrl.GetValue(),
                actionCtrl.GetValue(),
                iconCtrl.GetValue(),
                led_colorCtrl.GetStringSelection(),
                led_onCtrl.GetValue(),
                led_offCtrl.GetValue(),
                pictureCtrl.GetValue(),
                action_shareCtrl.GetValue(),
                action_button1Ctrl.GetValue(),
                action_label1Ctrl.GetValue(),
                action_button2Ctrl.GetValue(),
                action_label2Ctrl.GetValue(),
                action_button3Ctrl.GetValue(),
                action_label3Ctrl.GetValue(), 
                soundCtrl.GetValue(), 
            )

        
    def GetSelectedDevice(self):
        for device in self.plugin.devices:
            if device.name == self.devicesCtrl.GetStringSelection():
                return device

class AutoRemote(eg.PluginBase):

    class text:
        generalBox = "General Settings"
        port = "TCP/IP port:"
        documentRoot = "HTML documents root:"
        eventPrefix = "Event prefix:"
        authBox = "Basic Authentication"
        authRealm = "Realm:"
        authUsername = "Username:"
        authPassword = "Password:"


    def __init__(self):
        self.AddEvents()
        self.AddAction(SendMessage)
        self.AddAction(RegisterEventGhost)
        self.AddAction(SendNotification)
        self.running = False


    def __start__(
        self,
        prefix=None,
        port=1818,
        name="EventGhost",
        devices=[],
        publicIp="",
        authUsername="",
        authPassword="",
    ):
        self.info.eventPrefix = prefix
        if authUsername or authPassword:
            authString = base64.b64encode(authUsername + ':' + authPassword)
        else:
            authString = None
        class RequestHandler(MyHTTPRequestHandler):
            plugin = self
            environment = jinja2.Environment(loader=FileLoader())
            environment.globals = eg.globals.__dict__
            repeatTimer = eg.ResettableTimer(self.EndLastEvent)
        RequestHandler.basepath = None
        RequestHandler.authRealm = ""
        RequestHandler.authString = authString
        self.devices = devices
        self.port = port
        self.publicIp = publicIp
        self.name = name
        self.server = MyServer(RequestHandler, port)
        self.server.Start()


    def __stop__(self):
        self.server.Stop()


    def GetLabel(self,
        prefix="HTTP",
        port=1818,
        name="",
        devices="[]",
        publicIp="",
        authUsername="",
        authPassword=""):
    	return name

    def Configure(
        self,
        prefix="HTTP",
        port=1818,
        name="EventGhost",
        devices=[],
        publicIp="",
        authUsername="",
        authPassword="",
    ):
        text = self.text
        panel = eg.ConfigPanel()

        portCtrl = panel.SpinIntCtrl(port, min=1, max=65535)


        acv = wx.ALIGN_CENTER_VERTICAL
        sizer = wx.FlexGridSizer(2, 2, 5, 5)
        sizer.Add(panel.StaticText(text.port), 0, acv)
        sizer.Add(portCtrl)

            
        nameCtrl = panel.TextCtrl(name)
        sizer.Add(panel.StaticText("Name to appear on your device:"), 1, wx.EXPAND)
        sizer.Add(nameCtrl, 1, wx.EXPAND)  

        staticBox = wx.StaticBox(panel, label=text.generalBox)
        staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)
        staticBoxSizer.Add(sizer, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        panel.sizer.Add(staticBoxSizer, 0, wx.EXPAND)

        sizer = wx.FlexGridSizer(4, 2, 5, 5)

        self.deviceCtrl = panel.TextCtrl()
        sizer.Add(panel.StaticText("Device Name:"), 1, wx.EXPAND)
        sizer.Add(self.deviceCtrl, 1, wx.EXPAND)
        self.deviceCtrl.Bind(wx.EVT_KILL_FOCUS, self.OnNameChanged)  

        self.urlCtrl = panel.TextCtrl()
        sizer.Add(panel.StaticText("Device Personal URL (e.g. goo.gl/XxXxX) :"), 1, wx.EXPAND)
        sizer.Add(self.urlCtrl, 1, wx.EXPAND) 
        self.urlCtrl.Bind(wx.EVT_KILL_FOCUS, self.OnUrlChanged) 
            
        self.keyCtrl = panel.TextCtrl()
        sizer.Add(panel.StaticText("Device Key:"), 1, wx.EXPAND)
        sizer.Add(self.keyCtrl, 1, wx.EXPAND)
        self.keyCtrl.Disable()

        self.addDeviceCtrl = panel.Button("Add")
        sizer.Add(panel.StaticText(""), 1, wx.EXPAND)
        sizer.Add(self.addDeviceCtrl, 1, wx.EXPAND)  
        self.addDeviceCtrl.Bind(wx.EVT_BUTTON, self.OnAddDevice)
        self.addDeviceCtrl.Disable()

        self.devices = devices
        self.devicesCtrl = panel.Choice(0, [])
        for device in self.devices:
        	self.devicesCtrl.Append(device.name)
#       self.devicesCtrl.Bind(wx.EVT_CHOICE, self.OnSelectedDeviceChanged)
        sizer.Add(panel.StaticText("Existing Devices:"), 1, wx.EXPAND)
        sizer.Add(self.devicesCtrl, 1, wx.EXPAND)  

        self.removeDeviceCtrl = panel.Button("Remove")
        sizer.Add(panel.StaticText(""), 1, wx.EXPAND)
        sizer.Add(self.removeDeviceCtrl, 1, wx.EXPAND)  
        self.removeDeviceCtrl.Bind(wx.EVT_BUTTON, self.OnRemoveDevice)

        staticBox = wx.StaticBox(panel, label="Add Devices")
        staticBoxSizer = wx.StaticBoxSizer(staticBox, wx.VERTICAL)
        staticBoxSizer.Add(sizer, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        panel.sizer.Add(staticBoxSizer, 0, wx.EXPAND|wx.TOP, 10)



        publicIpCtrl = panel.TextCtrl(publicIp)
        sizer.Add(panel.StaticText("Your Public IP or Host Name (like a dyndns host name):"), 1, wx.EXPAND)
        sizer.Add(publicIpCtrl, 1, wx.EXPAND) 

        while panel.Affirmed():
            panel.SetResult(
            	"AutoRemote",
                portCtrl.GetValue(),
                nameCtrl.GetValue(),
                self.devices,
                publicIpCtrl.GetValue()
            )
            
    def OnAddDevice(self, event):
        self.GetDeviceFromInput()
        self.devices.append(self.deviceToAdd)
        self.devicesCtrl.Append ( self.deviceToAdd.name )
        if self.devicesCtrl.GetValue() == -1:
        	self.devicesCtrl.SetSelection ( 0 )
        print self.devices
        self.addDeviceCtrl.Disable()

    def OnRemoveDevice(self, event):
        index = self.devicesCtrl.GetValue()
        if index != -1:
            del self.devices[index]
            self.devicesCtrl.Delete(index)
    	
    def OnUrlChanged(self, event):
    	self.UpdateButton()
    	
    def OnNameChanged(self, event):
    	self.UpdateButton()
			
    def UpdateButton(self):
    	self.GetDeviceFromInput()
    	self.keyCtrl.SetValue(self.deviceToAdd.key)
    	if self.deviceToAdd.key != "Invalid URL":
		found = False
		for device in self.devices:
			if device.name == self.deviceCtrl.GetValue():
				found = True
				break
		if found:
			self.addDeviceCtrl.Disable()
			self.addDeviceCtrl.SetLabel("Name already exists")
		else:
			self.addDeviceCtrl.SetLabel("Add")
			self.addDeviceCtrl.Enable()
    	
    def GetDeviceFromInput(self):
    	addedDeviceName = self.deviceCtrl.GetValue()
    	self.deviceToAdd =  AutoRemoteDevice(addedDeviceName, self.urlCtrl.GetValue())
    	
#    def OnSelectedDeviceChanged(self, event):
#   	    if self.devicesCtrl.GetValue() != -1:
#            self.removeDeviceCtrl.Enable()

    	
class AutoRemoteDevice:
    
    name = None
    url = None
    key = None

    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.key = self.GetKey(self.url)
    
    def __str__(self):
        return self.name + "; " + self.url

    def __repr__(self):
        return self.__str__()

    def GetKey(self, shortUrl):
        if not shortUrl == '':
            try:
                import urllib
                if not "http://" in shortUrl:
                    shortUrl = "http://" + shortUrl
                result = urllib.urlopen('https://www.googleapis.com/urlshortener/v1/url?shortUrl={0}'.format(shortUrl)).read()
                import json
                resultObj = json.loads(result)
                url = resultObj["longUrl"]
                import urlparse
                parsed = urlparse.urlparse(url)
                key = urlparse.parse_qs(parsed.query)['key'][0]
                print key
                return key
            except KeyError:
                return "Invalid URL"
        else:
            return "Invalid URL"