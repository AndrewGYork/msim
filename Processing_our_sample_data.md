# Finding the data #

1. Start **ipython** in pylab mode (as described [here](http://code.google.com/p/msim/wiki/Installing_Python#Done_yet?))

2. Using the ["cd" command](http://en.wikipedia.org/wiki/Cd_(command)), (which stands for "change directory"), navigate to the "code" folder in the "Code with sample data v1p0" directory

  * **NOTE:** This is where `process.py` and `array_illumination.py` are located

https://sites.google.com/site/msimdocumentation/sample-processing/changing%20directory.JPG


# Processing the data #

1. In the **ipython** window, type "run process.py" and press enter

https://sites.google.com/site/msimdocumentation/sample-processing/processing1.JPG

3. The following screen will pop up and ask you to select a raw SIM data file for processing

  * Navigate to the "raw\_images" folder, in the "data" folder, in the "Code with sample data v1p0" directory
  * Select the file "tubules\_488\_z1.raw"

https://sites.google.com/site/msimdocumentation/sample-processing/processing2.JPG

4. After selecting "tubules\_488\_z1.raw," the following box will appear asking you to define the basename for the dataset by replacing the variables with question marks

  * This allows the program to find all the files belonging to that dataset
  * In our case, change "tubules\_488\_z1.raw" to "tubules\_488\_z?.raw"

https://sites.google.com/site/msimdocumentation/sample-processing/processing3.JPG

4. Press OK, and **ipython** will now look like this

https://sites.google.com/site/msimdocumentation/sample-processing/processing4.JPG

5. Verify that both "tubules\_488\_z1.raw" and "tubules\_488\_z2.raw" are listed and then press enter

6. The following window will pop up asking for you to select the lake to use

  * Select the file "lake.raw" (located within the "data" folder in the "Code with sample data v1p0" directory

https://sites.google.com/site/msimdocumentation/sample-processing/processing5.JPG

7. The following window will then pop up asking if you want to use the lake to determine the offset (See [footnote 1](http://code.google.com/p/msim/wiki/Processing_our_sample_data#1) for explanation).

  * Select "no"

https://sites.google.com/site/msimdocumentation/sample-processing/processing6.JPG

8. The following 4 figures should appear (See [footnote 2](http://code.google.com/p/msim/wiki/Processing_our_sample_data#2) for explanation).

https://sites.google.com/site/msimdocumentation/sample-processing/processing7.JPG

https://sites.google.com/site/msimdocumentation/sample-processing/processing8.JPG

https://sites.google.com/site/msimdocumentation/sample-processing/processing9.JPG

https://sites.google.com/site/msimdocumentation/sample-processing/processing10.JPG

9. Return to **ipython** (which should look as below) and press enter 3 times

https://sites.google.com/site/msimdocumentation/sample-processing/processing11.JPG

10. The SIM data is now processing

https://sites.google.com/site/msimdocumentation/sample-processing/processing12.JPG

11. When it is finished, **ipython** will look like this

  * As there are only 2 small files to be processed, this should only take a minute or so, depending on how fast your computer is

https://sites.google.com/site/msimdocumentation/sample-processing/processing14.JPG


# Opening the processed SIM images in ImageJ #

1. Install [\*ImageJ\*](http://rsbweb.nih.gov/ij/) if you do not already have it

2. In **ImageJ**, go to “File,” then “Import,” and select “Raw”

3. Navigate to the "raw\_images" folder, in the "data" folder, in the "Code with sample data v1p0" directory

4. Select "tubules\_488\_z\_enderlein\_stack.raw"

https://sites.google.com/site/msimdocumentation/sample-processing/opening1.JPG

5. When the “Import” window appears, set the following parameters

https://sites.google.com/site/msimdocumentation/sample-processing/opening2.JPG

6. Click “OK”

7. Check out the processed image

  * **NOTE:**For file size reasons, this is a very small stack, of a very small field of view

https://sites.google.com/site/msimdocumentation/sample-processing/opening3.JPG

# Footnotes #
#### 1 ####
As described in our paper's [supplementary note 4](http://www.nature.com/nmeth/journal/vaop/ncurrent/extref/nmeth.2025-S1.pdf), we have to identify the "offset vector" of each raw data image. If your system is thermally stable and repeatable, you often get the best measurement of this offset vector by inspecting the high-signal-to-noise reference "lake" data, and assuming the illumination spots are in the same positions when you take your raw data images. However, if your system is not thermally stable, or if you wait a long time between taking your reference "lake" data and taking your raw data images, the spots may drift to different positions.

On the other hand, if your raw image data has high signal-to-noise, you can often get a good measurement of the "offset vector" directly from your raw image data. If your sample is sparse or dim, however, this may give inaccurate results.

Bottom line: try processing one way. If the images are lousy, try processing the other way.

#### 2 ####
As described in our paper's [supplementary note 4](http://www.nature.com/nmeth/journal/vaop/ncurrent/extref/nmeth.2025-S1.pdf), we have to figure out precisely where the illumination spots are in each raw image. The four figures that pop up help you tell if our code is doing a good job guessing where the illumination spots are.

##### Figure 1 #####
The illumination spots form a periodic lattice in real space, so the sum of the Fourier magnitudes of the raw data should form a periodic lattice in Fourier space. If you can't see a periodic lattice of spikes, something's wrong.

##### Figure 2 #####
To determine the offset vector, we take a 'lattice average' the first frame of image data. If we've correctly determined the periodicity of the lattice shown in Figure 1, the 'lattice average' image in Figure 2 should look like a few round blobs. If your sample is very sparse, or very dim, this image may be very poor, and the offset vector may not be accurate. Consider using the reference "lake" data to calculate the offset vector, as described in [footnote 1](http://code.google.com/p/msim/wiki/Processing_our_sample_data#1). If you're already using your lake data to calculate the offset vector, and this lattice average still looks nasty, something's wrong. Take brighter/better lake data, or go bug-hunting.

##### Figure 3 #####
Once we know the periodicity of the lattice in Figure 1, we can look at the Fourier phase of each raw data image at the spike positions, and use this information to estimate how much the illumination spots shift each frame. We subtract the phase predicted by this estimate from the measured phase, and plot this residual phase in Figure 3. Hopefully this resembles low-amplitude noise. If this residual phase approaches π, we ignore that spike in our estimate of the shift vector. If the phase of all of the spikes approach π, we probably have a terrible estimate of the shift vector.

##### Figure 4 #####
This one's easy. We just show a raw data frame, and put a red dot everywhere we think there's an illumination spot. A good sanity check. Note that we draw these dots as a raster rather than vector graphic, so the display is only accurate to the nearest pixel; internally, these positions are stored with more precision.