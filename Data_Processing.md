

# Processing the data #
1. Open _pylab_ (found in RAID(D)\SIM\_data) by double-clicking
  * Type “run process.py” and press enter

https://sites.google.com/site/msimdocumentation/data-processing/processing1.JPG

2. The following screen will pop up and ask you to select a raw SIM data file for processing

  * Open the FOV folder containing the data you want to process
  * Select one of the raw data files that is representative of the dataset you want to process
  * **NOTE:** if there are multiple datasets (different filters and/or lasers) within a FOV folder, these will need to be processed separately

https://sites.google.com/site/msimdocumentation/data-processing/processing2.JPG

3. After selecting a sample data file, the following box will appear asking you to define the basename for the dataset by replacing the variables with question marks

  * **EX:** If all your images are saved as “GFP\_c488\_f1\_z####.raw” (z0001, z0002, z0003, etc.), then replace the numbers after z with question marks, making the basename “GFP\_c488\_f1\_z????.raw”
  * **NOTE:** If it is also a time series, then the numbers after the t must also be replaced with question marks
  * This allows the program to find all the files belonging to that dataset within your selected FOV folder

https://sites.google.com/site/msimdocumentation/data-processing/processing3.JPG

4. Press OK, and _pylab_ will now look like this

https://sites.google.com/site/msimdocumentation/data-processing/processing4.JPG

5. Verify that all the files in the dataset you want to process are listed and then press enter

6. The following window will pop up asking for you to select the lake to use

  * **NOTE:** the window will automatically go to the folder one level above the FOV folder the dataset you selected is in; if your lake is not saved here, then you will have to go find it

https://sites.google.com/site/msimdocumentation/data-processing/processing5.JPG

7. Select the lake to use (based on the laser and filter used to take the dataset you are processing)

8. The following window will then pop up asking if you want to use the lake to determine the offset

  * If your dataset is sparse and/or dim, then you should select yes, and the lake will be used to determine the position of the array
  * If your dataset is dense and bright, then you should select no, and the dataset itself will be used to determine the position of the array
  * **NOTE:** when in doubt, start by selecting yes, and then if you have problems later (see step 11c below), you can redo the above process and select no instead

https://sites.google.com/site/msimdocumentation/data-processing/processing6.JPG

9. _pylab_ should now look like this and 4 figures (corresponding to the lake file) will appear

https://sites.google.com/site/msimdocumentation/data-processing/processing7.JPG

  * Verify that they look close to the following images

https://sites.google.com/site/msimdocumentation/data-processing/processing8.JPG

https://sites.google.com/site/msimdocumentation/data-processing/processing9.JPG

https://sites.google.com/site/msimdocumentation/data-processing/processing10.JPG

  * **NOTE:** these peaks should be less than 1 (and definitely less than 3)

https://sites.google.com/site/msimdocumentation/data-processing/processing11.JPG

  * **NOTE:** each red dot should fall within a white/light gray spot

10. If the figures look fine, press enter once to view the actual data

  * _pylab_ should look like the screen below

https://sites.google.com/site/msimdocumentation/data-processing/processing12.JPG

  * The following 2 figures (corresponding to frame 0 of image 0) should also appear
  * **NOTE:** If you selected "yes" for "Use lake to determine offset," then only the first figure will appear

https://sites.google.com/site/msimdocumentation/data-processing/processing13.JPG

11. Press enter once and then type “20” and press enter again in order to see image 20

  * **NOTE:** 20 was chosen arbitrarily here - chose a number roughly halfway through your z-stack that has a good amount of signal on it (look at the image within _ImageJ_ to determine a good slice)
  * _pylab_ should look like the screen below

https://sites.google.com/site/msimdocumentation/data-processing/processing14.JPG

  * The following figure (corresponding to frame 0 of image 20) should also appear

https://sites.google.com/site/msimdocumentation/data-processing/processing15.JPG

  * **NOTE:** each red dots should be centered in white/light gray spots
    * If this is not true, close _pylab_, redo steps 1-7, then select “no” in step 8, and continue from there

12. Type 1 and then press enter to see frame 1 of image 20 and verify the red dots correspond to the white/light gray spots as in step 8

  * **NOTE:** we also want to verify that the intensity of each dot varies as we move from one frame to the next
  * _pylab_ should look like the screen below

https://sites.google.com/site/msimdocumentation/data-processing/processing16.JPG

  * The following figure (corresponding to image 20) should also appear

https://sites.google.com/site/msimdocumentation/data-processing/processing17.JPG

13. Repeat step 9 for frame 2 of image 20 by typing 1 and then press enter

  * _pylab_ should look like the screen below

https://sites.google.com/site/msimdocumentation/data-processing/processing18.JPG

  * The following figure (corresponding to image 20) should also appear

https://sites.google.com/site/msimdocumentation/data-processing/processing19.JPG

14. Repeat for multiple frames until you are sure that the red dots correspond to the white/light gray spots and the intensity of those spots is changing between frames

  * Then press enter twice to start the computer processing of the data
  * _pylab_ should look like the following screen as it begins to process the data

https://sites.google.com/site/msimdocumentation/data-processing/processing20.JPG

  * As the processing continues, the screen will look like this
    * You can keep track of the image and frames currently being processed by looking at this screen - for example, frames 110-119 of image 9 are currently being processed

https://sites.google.com/site/msimdocumentation/data-processing/processing21.JPG

15. Repeat for each channel and FOV by following steps 1-11 above

  * This will generate an enderlein\_image and widefield file for each file and a stack for each dataset (channel/FOV)


# Deconvolution #
1. Open a stack of beads taken under the same conditions (laser, filter, and objective)

  * In _ImageJ_, go to “File” and then “Open”
  * Find where the appropriate PSF(s) are located (for laser/filter, oil/silicone, and step size used)
  * **NOTE:** On the LMF-BACKUP1 server, there is a folder labeled "PSFs" located with the "Hari Shroff" folder that contains PSFs for various combinations of laser/filter, oil/silicone, and step size
  * Select “psf\_oil/silicone\_laser\_stepsize\_16bit” as necessary

2.Open the enderlein\_image stack that was created for one data set:

  * Go to “File,” then “Import,” and select “Raw”
  * Find the folder within which you saved the data
  * Select “basename\_c###_f#_z\_enderlein\_stack.raw”
  * When the “Import” window appears, set the following parameters

https://sites.google.com/site/msimdocumentation/data-processing/decon1.JPG

  * Click “OK”

3. Create a max projection:

  * Go to “Image,” then “Stacks,” and select “Z Project”
  * Leave the Start and Stop slices as they are and change the “Projection Type” to “Max Intensity”

https://sites.google.com/site/msimdocumentation/data-processing/decon2.JPG

  * Click “OK”

4. Press “Ctrl + Shift + C” to open B&C window

  * With the max projection selected, press “reset” and then “set”

https://sites.google.com/site/msimdocumentation/data-processing/decon3.JPG

  * Click box (propagate to all open images) and press ok

https://sites.google.com/site/msimdocumentation/data-processing/decon4.JPG

5. Go to “Image,” then “Type,” and select “16-bit”

6. Save resulting image as a tif

7. Go to “Plugins,” then “Parallel Iterative Deconvolution,” and select “3D Iterative Deconvolution”

8. In the resulting window, set the following parameters:

https://sites.google.com/site/msimdocumentation/data-processing/decon5.JPG

  * Image: select the 16-bit image you just created
  * PSF: select the correct bead stack for your sample (based on filter, not laser!)
  * **NOTE:** If not doing anything else on the computer, you can set “Max number of threads” to 8 for a faster decon

9. Press “Deconvolve” and wait for the deconvolved image to appear

10. Save resulting image as a tif