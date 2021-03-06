eg.RegisterPlugin(
    name = "SconiPlug-USB",
    author = "Hinterbenkler",
    version = "1.0." + "$LastChangedRevision: 302 $".split()[1],
    kind = "remote",
    description = (
        'Plugin for Sconi-USB receiver. '
	'Since the Sconi driver is compatible '
	'with Igor Cesko\'s USB IR receiver, '
	'but without annoying start dialog, '
	'you can replace the Igor USB driver '
	'with the one downloaded at '
	'<a href=http://www.myhtpc.de/tools/irshop/usb_girder_plugin.zip>www.myhtpc.de/tools/irshop/usb_girder_plugin.zip</a>.'
    ),
)


from thread import start_new_thread
from  ctypes import windll, byref, c_ubyte, c_int, create_string_buffer
from threading import Timer, Event
from time import clock, sleep


SAMPLE_TIME = 0.0000853


class SconiPlugUSB(eg.RawReceiverPlugin):
    
    def __init__(self):
        eg.RawReceiverPlugin.__init__(self)
        self.irDecoder = eg.IrDecoder(SAMPLE_TIME)
        
        
    def __start__(self):
        self.dll = None
        self.threadShouldStop = False
        try:
            self.dll = windll.Sconi
        except:
            raise eg.Exception("No Sconi-USB V.1 driver installed!")
        start_new_thread(self.ReceiveThread, ())
    
    
    def __stop__(self):
        self.threadShouldStop = True
        
        
    def ReceiveThread(self):
        dll = self.dll
        timeCodeDiagram = (c_ubyte * 256)()
        diagramLength = c_int(0)
        portDirection = c_ubyte()
        dll.DoGetDataPortDirection(byref(portDirection))
        portDirection.value |= 3
        dll.DoSetDataPortDirection(portDirection)
        dll.DoSetOutDataPort(1)
        Decode = self.irDecoder.Decode
        self.flashThreadIsRunning = False
        while not self.threadShouldStop:
            dll.DoGetInfraCode(timeCodeDiagram, 0, byref(diagramLength))
            if diagramLength.value:
                self.StartLedFlashing()
                event = Decode(timeCodeDiagram, diagramLength.value)
                self.TriggerEvent(event)
            else:
                sleep(0.01)
        dll.DoSetOutDataPort(0)
        self.dll = None
        
        
    def StartLedFlashing(self):
        self.ledTimeout = clock() + 0.1
        if not self.flashThreadIsRunning:
            self.flashThreadIsRunning = True
            start_new_thread(self.LedFlashingThread, ())
            
            
    def LedFlashingThread(self):
        while self.ledTimeout > clock():
            self.dll.DoSetOutDataPort(3)
            sleep(0.08)
            self.dll.DoSetOutDataPort(1)
            sleep(0.08)
        self.flashThreadIsRunning = False