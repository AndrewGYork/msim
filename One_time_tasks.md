

# Generating an illumination stack for the DMD #
  * **NOTE:** you don’t have to do this each time, only when you want to change the pattern

1. Open _dmd\_illumination\_stack.py_ by right clicking the file and selecting “Edit with IDLE”

  * Location: RAID(D)\SIM\_data\python

2. In _dmd\_illumination\_stack.py_, modify the “half distance”

  * _half\_distance_: determines how spread out the illumination spots are and therefore how many images must be taken to cover the entire FOV (yellow arrow)
  * The default is 8, which corresponds to 224 images (227 when counting the first 3 images which are not recorded) and should take ~1 second to display
  * Increasing this number spreads out the spot, which means more images are taken and it takes longer to display (each image takes 4.5 ms to display)
  * Do not modify this without talking with Andy first!

https://sites.google.com/site/msimdocumentation/one/dmd_illumination_stack.JPG

3. Save the file

4. Go to “Run” and then select “Run module” (or just click F5) to generate the illumination pattern

# Taking a background image #
1. In _sim\_scope.py_, set the parameters to the same values as for the lake

2. Manually shutter the 488 nm and/or 561 nm laser(s)

https://sites.google.com/site/msimdocumentation/home/manual%20shutter.JPG

3. Save _sim\_scope.py_ and then press F5 to run the program

4. This will bring up a window asking you to select the folder in which to save the files as well as the basename (ex: "background") to use for those files

  * **NOTE:** You do not need to take this for both lasers
  * **NOTE:** Once the background has been taken once, then it can be used for all future data acquisition