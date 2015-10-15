# News #
We've built a [new, analog version of the multifocal structured illumination microscope](http://dx.doi.org/doi:10.1038/nmeth.2687), called the 'instant SIM'. It's a lot faster:

<a href='http://www.youtube.com/watch?feature=player_embedded&v=ZGdVZ2ugZZo' target='_blank'><img src='http://img.youtube.com/vi/ZGdVZ2ugZZo/0.jpg' width='425' height=344 /></a>

Quick overview of the new device's capabilities:
  * 3D superresolution (145 nm transverse, 350 nm axial resolution)
  * Uses standard fluorescent probes (like GFP), currently configured for 488 and 561 nm illumination
  * Works in thick samples (>50 microns). Previous SIM scopes couldn't do this.
  * Very fast (>100 2D slices per second)
  * Live-cell compatible (tens or hundreds of 3D volumes)
  * Low photobleaching (similar to a spinning disk confocal)
  * 100x100 micron field of view

The relevant source code for the instant SIM can be found [here](http://code.google.com/p/msim/source/browse/), but at the moment, this site mostly describes the previous version, the multifocal SIM:

<a href='http://www.youtube.com/watch?feature=player_embedded&v=4RSGylmEgL0' target='_blank'><img src='http://img.youtube.com/vi/4RSGylmEgL0/0.jpg' width='425' height=344 /></a>

# Introduction #
Fluorescence microscopes are an awesome tool for biologists, but get blurry if you zoom in too much. It turns out you can remove some of this blur if you illuminate your sample with sharply structured patterns, and collect images of the resulting glow while varying the pattern. (See [structured illumination microscopy (SIM)](http://www.ncbi.nlm.nih.gov/pubmed/10810003), for example).

A drawback of this trick is that the raw data from your microscope looks like gibberish:

<a href='http://www.youtube.com/watch?feature=player_embedded&v=TBZ1wtfg7jg' target='_blank'><img src='http://img.youtube.com/vi/TBZ1wtfg7jg/0.jpg' width='425' height=344 /></a>

You need software to turn this data into a super-resolution image like this one:

<a href='http://www.youtube.com/watch?feature=player_embedded&v=ZigQRD6ONEE' target='_blank'><img src='http://img.youtube.com/vi/ZigQRD6ONEE/0.jpg' width='425' height=344 /></a>

That's what 'msim' does.

Specifically, we built a new kind of fluorescence microscope, which we call a 'multifocal structured illumination microscope' (MSIM). Distinguishing features:
  * 3D superresolution (145 nm transverse, 400 nm axial resolution)
  * Uses standard fluorescent probes (like GFP), currently configured for 488 and 561 nm illumination
  * Works in thick samples (>50 microns). Previous SIM scopes couldn't do this.
  * Reasonable speed (1 2D slice per second)
  * Live-cell compatible (tens or hundreds of 3D volumes)
  * Low photobleaching (similar to a spinning disk confocal)
  * 50x50 micron field of view

Functionally, it's a lot like a point-scanning confocal with twice the resolution and higher signal-to-noise, at the cost of digital post-processing.

# Getting started #

If you're just curious how it works, check out [our paper](http://dx.doi.org/10.1038/nmeth.2025) first. The code won't make much sense unless you read the paper. Once you've got the basic idea, we have some [sample data](http://code.google.com/p/msim/downloads/list) and a step-by-step walkthrough how to [install Python](http://code.google.com/p/msim/wiki/Installing_Python), [install our code](http://code.google.com/p/msim/wiki/Installing_our_code), and [process the sample data into a superresolution image](http://code.google.com/p/msim/wiki/Processing_our_sample_data).

If you want to use the microscope we built, contact [our lab at the NIH](http://www.nibib.nih.gov/Research/Intramural/HighResolutionOpticalImaging). If you can see hints of your structure-of-interest in a spinning disk or point-scanning confocal microscope, but you need a little more resolution, we can probably help. Kelsey Temprine wrote walkthroughs of [data acquisition](http://code.google.com/p/msim/wiki/Data_Acquisition), [data processing](http://code.google.com/p/msim/wiki/Data_Processing), and [other details](http://code.google.com/p/msim/wiki/One_time_tasks) for our MSIM users at the NIH.

If you want to build your own MSIM, great! The hardware is a fairly simple modification to an existing widefield microscope. The software is open-source. With the relevant parts ordered, I can build one in about a day. Send us an email, we might be able to help with construction.