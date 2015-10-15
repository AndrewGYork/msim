# If you just want to process sample data #

Download our most recent [code with sample data](http://code.google.com/p/msim/downloads/list). Unzip the folder somewhere convenient (maybe your desktop for now). If you've already [installed python and the python subpackages we need](http://code.google.com/p/msim/wiki/Installing_Python), you should be ready to [run our code](http://code.google.com/p/msim/wiki/Processing_our_sample_data).

# Providing your own data #

If you want to provide your own data, it matters how you organize your data files. The sample code provides a reference for where the different types of files should go. Open up the 'Code with sample data' folder, and browse through the contents. Here's what each of these files is doing.

  * `array_illumination.py` is a module of functions for processing raw MSIM data into high-resolution images. It needs to go somewhere on [python's search path](http://docs.python.org/tutorial/modules.html#the-module-search-path).

  * `process.py` is a script which calls functions from `array_illumination.py`. This is the script we run to process raw MSIM data into high-resolution images. It doesn't matter where this file goes, as long as you know how to run it from within ipython. However, it's not a bad idea to keep `array_illumination.py` in the same folder as `process.py`, and run ipython from within this folder.

The rest of the files are hardware-specific, and included only so you can run the processing software without building your own MSIM scope:

  * `background.raw`: several camera images, taken with no illumination. Must be in the same directory as `array_illumination.py`. Must have the same pixel dimensions as the images you want to process, taken on the same region-of-interest of the same camera.

  * `hot_pixels.txt`: A list describing defective camera pixels to be ignored. Must be in the same directory as `array_illumination.py`. Coordinate 0, 0 is a corner of the raw image; if you change your camera's region of interest, you have to change `hot_pixels.txt` too.

  * `lake.raw`: Reference MSIM data taken of a uniform fluorescent object. Useful for flat-fielding MSIM images, and determining where illumination spots are located. Should be in the parent directory of the MSIM data your processing. Like `background.raw`, it must have the same pixel dimensions as the images you want to process, taken on the same region-of-interest of the same camera. We take fresh lake data every day, although I'm not sure we need to.

  * `tubules_488_z?.raw`: MSIM data of fixed U2OS cells stained with Alexa 488. I cropped the heck out of these images, and only included two z-slices, so that the file size would not be prohibitive. Usually we have one folder for each field of view we image.

# Hardware control code #
I suspect most folk will write their own hardware control code. I've [shared ours here](http://code.google.com/p/msim/source/browse/#hg%2Fhardware_control) in case it helps out other similar nerds. It's not very well documented, but if you're building your own SIM scope, you probably know a bit about programming. Feel free to get in touch if you want guidance.

  * [`dmd.py`](http://code.google.com/p/msim/source/browse/hardware_control/dmd.py) controls a Texas Instruments digital micromirror device. We paid about $5k for [the hardware](http://www.ti.com/tool/dlpd4x00kit), but they snookered us; it cost another $10k for the [DLL](http://www.dlinnovations.com/products/alp4-HS.html?loco=d4100&name=D4100) that lets you run the hardware at full speed. It's still a good deal for an awesome piece of hardware, but man was I mad when I realized I needed another $10k. Read the Supplementary Materials from [our paper](http://dx.doi.org/10.1038/nmeth.2025) for a description of some quirks of this device. I'm told you don't need their $10k software if you can program in VHDL, but I surely do not know how to do that.

  * [`pco.py`](http://code.google.com/p/msim/source/browse/hardware_control/pco.py) controls a [PCO scientific CMOS camera](http://www.pco.de/categories/scmos-cameras/pcoedge/). This camera costs about $20k, but was essential for getting our scope operating at reasonable speeds. This is a blazing fast, low-noise camera, but be warned: it's still a bit 'engineering grade'. Don't expect everything to work easily, or as expected. Read the Supplementary Materials from [our paper](http://dx.doi.org/10.1038/nmeth.2025) for a description of some quirks of this device.

We wire the trigger output of the DMD to the trigger input of the sCMOS camera. (Things don't work as well if you use the camera as the master trigger). This required fiddling with a Molex connector on the DMD control board. If you're a Molex rookie, get some spare Molex connectors! You'll probably mess up the first one you try to assemble. Better yet, try to get the folks at [DLi](http://www.dlinnovations.com/) to sell you a cable with the right connector to access the trigger out.

I ran into a funny timing challenge between the PCO camera and the TI DMD. When you tell the DMD to start displaying frames, it sends out trigger pulses immediately. You have to start pulling frame buffers off the PCO camera immediately, or else it will start skipping triggers. I found the easiest way to get this timing right was to run the DMD control software in a subprocess, and have the subprocess pause a few tens of milliseconds after the main process tells it to activate the DMD.

The rest of the hardware ([shutters](http://code.google.com/p/msim/source/browse/hardware_control/shutters.py), [z-stage](http://code.google.com/p/msim/source/browse/hardware_control/stage.py), [filter wheel](http://code.google.com/p/msim/source/browse/hardware_control/wheel.py)) was easy to control through the serial port, using [pyserial](http://pyserial.sourceforge.net/).

All the hardware control code has to go somewhere on [python's search path](http://docs.python.org/tutorial/modules.html#the-module-search-path).