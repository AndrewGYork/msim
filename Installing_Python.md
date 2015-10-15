# Introduction #

In order to use our [processing code](http://code.google.com/p/msim/source/browse/), you need to have Python installed, along with several subpackages. Here's the packages and versions we've tested:

  * [Python 2.7.3](http://python.org)
  * [numpy 1.6.1](http://numpy.scipy.org/)
  * [scipy 0.10.1](http://scipy.org)
  * [matplotlib 1.1.0](http://matplotlib.sourceforge.net/)
  * [ipython 0.12](http://ipython.org/)

#### COMMON MISTAKE: ####
> If you install python 2.7.x, and try to use the numpy Windows installer for python 2.6.x, it won't work. The windows installer must match the version of python you have installed.

#### COMMON PROBLEM: ####
> On Windows, ipython depends on [setuptools](http://pypi.python.org/pypi/setuptools); install setuptools first

We've used this code in Windows 7 and Ubuntu 10.10.

On Windows machines, I typically use the binary installers found in the 'download' section of each package's website. 64-bit versions of these packages, compiled for Windows are [available here](http://www.lfd.uci.edu/~gohlke/pythonlibs/). Only do this if you know what you're doing.

On Ubuntu, I typically install these packages through [Synaptic Package Manager](https://help.ubuntu.com/community/SynapticHowto).

I've tried the processing code on Mac, but had a hard time, because [Python on a Mac is a fucking mess](http://stackoverflow.com/questions/5235617/what-is-the-best-way-to-install-python-2-on-os-x). If you have to use Mac for some reason, drop [George Patterson](http://www.nibib.nih.gov/Research/Intramural/Biophotonics/Patterson) a line; he's put some time into getting my code working on his Macintosh computers.

# A possible shortcut #

[Enthought](http://enthought.com/) is a great company that has put a lot of work into making Python useful for scientific work. They've put together a [free Python distribution](http://enthought.com/products/epd_free.php) that should include all the packages our software needs. However, I've never personally tried this distribution, so I can't vouch for it.

# Done yet? #
To check if you've successfully installed the required software, open an ipython window in 'pylab' mode. On Linux, I do this by opening a terminal and typing `ipython -pylab`. On windows, I typically do this by using the `pylab` shortcut from the ipython folder in the Start menu.

#### COMMON PROBLEM: ####
> As [described here](http://www.partofthething.com/thoughts/?p=466), IPython installation may not create ipython shortcuts in Windows. On my Windows machine, for example, I have to create a shortcut with this target: `C:\Python27\python.exe "C:\Python27\scripts\ipython-script.py" --pylab`

> If you used a different version of python or a different version of Windows, you may have to modify that target slightly. If this step stalls you, google it, or email me.

If all goes well, you should see a window like this after you start ipython:

http://sites.google.com/site/msimdocumentation/data-processing/processing1.JPG

(Except yours probably won't say 'run process.py')

You should be able to execute plotting commands, like `plot([1, 2, 4])`. If so, you're done! If not, get in touch with me, or spend some time searching Google. Alternatively, I believe Enthought will sell you support and training for their python distribution.