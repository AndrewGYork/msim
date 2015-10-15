# Introduction (UNDER CONSTRUCTION) #

For now, I'll just tell you how we built ours. Modifications require at least a little thinking. For example, the magnifications in the system are carefully chosen; if you want a bigger field of view, you'll probably need a bigger DMD chip. If you use a camera with different size pixels, you might have to change your emission-path tube lens.

# Parts we used #

  * Widefield microscope (Olympus IX-81 with right side port)
  * 60x [silicone oil objective](http://www.olympusamerica.com/seg_section/seg_silicone_oil_objectives.asp) (good for going deep)
  * A low-magnification objective that's parfocal with the 60x objective, useful for axial alignment.
  * [pco.edge](http://www.pco.de/categories/scmos-cameras/pcoedge/) camera (important for high noise, low frame rate)
  * [Texas instruments DMD](http://www.dlinnovations.com/products/d4100.html), plus a [~$10k software package](http://www.dlinnovations.com/products/alp4-HS.html?loco=d4100&name=D4100) to run the DMD at full speed. The DMD we used was actually intended for infrared use, I think, but it's what we had lying around. You can get one intended for visible light.
  * An unusual dichroic that transmits 405, 488, and 561 nm light, and reflects our fluorescence emission. This started as a design fluke for historical reasons, but turned out to be very important for diagnosing aberrations.
  * A pair of Thorlabs achromatic doublets arranged as a 1.5x magnification telescope in our illumination arm
  * Fairly high-power excitation lasers (>100 mW each, 488 nm and 561 nm.) Our emission path is simple and efficient, but our illumination path is extremely inefficient, so high power here is crucial for good signal levels.
  * Molex connector for the trigger-out signal of the DMD. Make sure to ask for this part when you order the DMD; ideally, buy a cable intended for this use when you buy the DMD. This was actually fairly annoying; I had trouble crimping the wires to fit the Molex connector, and got a flaky connection the first time I thought I'd succeeded.
  * A nice heavy optical table to reduce vibration.
  * An acquisition computer with a fast hard drive (ours has a 500 GB RAID), running Windows (I can't remember if the pco.edge or the DMD have Linux support, and I never tried). Multiple cores are nice, if you also want to use this machine to process your SIM data.

# Rough construction procedure #

## How to align a lens ##
Most of the effort of constructing the illumination arm consists of putting lenses in the beam path the right way. You generally want your lenses co-axial, not tilted relative to one another, and with each consecutive lens pair separated by the sum of their focal lengths. Also, for the lenses we used, I believe you're supposed to place the flat side of the lens facing towards pointlike sources, and the curved side facing towards collimated beams.

I find it easiest to align lenses precisely by watching their effect on a reference beam. If a lens is placed in a reference beam without laterally deflecting the beam, you know that the lens is co-axial with the beam. If the back-reflection from the first lens surface points back along the reference beam, you know the lens is not tilted with respect to the beam. If any two consecutive lenses take a collimated beam in, and give a collimated beam back out, you know they're separated by the sum of their focal lengths. Using these three guides (non-deflection, back-reflection, preserve collimation), we can align the lenses in our illumination path. It's easiest to judge collimation and deflection if the reference beam propagates a long distance, so consider using a mirror to reflect your outgoing reference beam to a distant wall.

## Align the illumination-path lenses ##

Start with a well-collimated reference beam (we used our 488 nm laser). The diameter of this beam should be enough to fill your DMD. You should have at least two mirrors between your source and the microscope, so you can adjust the position and angle of the reference beam by adjusting the position and angle of these mirrors.

If you can, remove both your tube lens and your objective. Then, remove and replace the tube lens while tweaking the reference beam. When the back reflection and non-deflection tests are satisfied for the tube lens, your reference beam is set. If you can't remove your tube lens, I guess you have to eyeball this step.

Next, attach your objective to the microscope. Ideally, you would adjust the objective and tube lens to ensure they're co-axial. Probably, you have to trust your microscope manufacturer to have done this correctly. Is your microscope's objective one focal length away from the tube lens? The objective/tube lens should preserve collimation. You can check by moving the objective up and down (if it's on an axial positioner) while watching the output beam's divergence. Hopefully, when the objective's axial position minimizes divergence, the objective will also be nearly the right distance from your coverslip. If not, consider figuring out how to adjust the coverslip axial position.

Now, add the Thorlabs achromat lenses to the illumination path one at a time, starting closest to the sample. Put the shorter focal length achromat closer to the sample, to shrink the image of the DMD by 1.5x on its way to the sample. Each consecutive lens pair should preserve collimation, non-deflection, back-reflection. We found it helpful to remove or replace the objective so there's always an even number of lenses in the system; collimation and deflection can be difficult to judge if your outgoing beam diverges too rapidly. Since the DMD will be used with a sparse pattern of pointlike sources, place the flat side of the lens closest to the DMD facing the DMD. The beam from each pointlike source will be collimated after this lens, so place the curved surface of the next lens facing the DMD.

## Align the emission path ##

Now that we have the 1.5x telescope, tube lens, and objective co-axial, it's a good time to align the emission path. There are only a few optics in the emission path (objective, dichroic, emission-path tube lens, barrier filter, camera). There are two tricks: getting the camera the right distance from the sample, and making sure the dichroic is flat.

In our scope body (Olympus IX-81 with right side port), the dichroic and emission-path tube lens are not adjustable, so the only real alignment is camera position. We found that attaching the pco.edge directly to the scope body was a bad idea, since the fan in this camera caused unacceptable vibration in the sample. However, mounting the pco.edge to the optical table with no direct mechanical link between the scope body and the camera solved the problem.

With an even number of lenses in the illumination path, the objective should produce a collimated beam. If we remove the first lens in the 1.5x illumination path telescope, the objective should now produce a focused beam at the 'right' depth in the sample. If your sample is a uniform fluorescent target (for example, dye solution sandwiched between two coverslips), you can use the resulting fluorescence to position your camera. Center the fluorescence on the region of the chip you plan to use. The readout time of the pco.edge depends on the size of the region of interest, and the region of interest is not smoothly adjustable on this chip, so good centration is important for high-speed imaging.

We found it easiest to switch to a low-magnification objective (Olympus 10x air) for positioning the camera axially, since axial demagnification scales like the square of lateral magnification. I'm not sure this objective was actually parfocal with our 60x silicone objective, but if it wasn't, I couldn't tell the difference. Slide the camera around on the optical table until the point-like fluorescence is centered and in-focus, and bolt the camera down.

After aligning the camera for the first time, we noticed that the image of the fluorescence from our focused beam looked very strange, like the letter X instead of a nice round blob. It turns out this was because our dichroic was not flat enough. It was very lucky for us that we were using a dichroic which reflects emission light; if we'd been using a more 'normal' dichroic which reflects excitation light, we probably would not have noticed that our focused spot was not tight, and would never have gotten good resolution. I suspect that most dichroics used in commercial microscopes are not very flat, but it doesn't matter for many applications.

We switched our initial dichroic for a thicker one (3 mm instead of 1), which improved our emission PSF. The next few hours were pretty lousy. Over and over, we removed our dichroic, changed the tightness of its mounting screws, put it back, and checked our emission PSF. Eventually, we found a tightness level (not too tight, not too loose) that resulted in a reasonably nice PSF, and we never touched it again. If you build your own SIM, give serious thought to how you will make sure your dichroic is flat. Thickness? Mounting tension? Probably it's easiest to just use the thickest dichroic your scope body will allow.

## Positioning the DMD ##
With the 1.5x illumination path telescope in place, the camera correctly axially positioned, and the dichroic flat, it's time to position the DMD. Since the DMD is a reflective optic, you'll need to reposition your reference beam. Before you move your reference beam, make a note of approximately where the DMD should go; we measured one focal length away from the illumination telescope along the reference beam (with a ruler), and placed the DMD so the reference beam was hitting squarely centered on its back.

With the lateral and axial position of the DMD fixed, you just have to set the angle. I didn't come up with a precise way to do this, instead I just tried to eyeball the DMD surface approximately perpendicular to the optical axis of the rest of the illumination path.

Once the DMD is approximately centered, we move the reference beam. Since the individual DMD mirrors rotate about a diagonal axis, you have to 'feed them diagonally' (see our paper's [supplementary figure 3](http://www.nature.com/nmeth/journal/vaop/ncurrent/extref/nmeth.2025-S1.pdf)). There's a border of permanently deflected mirrors around the DMD perimeter, so there's only one 'right' corner to feed in your beam from. Trial and error should work pretty quickly to figure out which corner is right. You can use the software that comes with the DMD to turn all the pixels 'on'; you'll know when the reference beam is positioned correctly, because the beam reflecting from the DMD will be centered on the optical axis of the system. Since we almost always operate the DMD with a very sparse pattern of pixels, this alignment is not crucial, but I still try to be careful about it.

## Just a little electronics ##

For high-speed operation, we need to connect the trigger-out of the DMD to the trigger-in of the pco.edge. Try to discuss this application with DLi before you buy your DMD, and try to get them to make you an appropriate cable (Molex on one end, SMA on the other). I ended up improvising a solution, which worked, but was annoying to construct. The manual that comes with the DMD should show which pin on which connector is the trigger-out pin.

## Vibration isolation ##

We use Thorlabs SH05 shutters for our illumination lasers, because they're easy to control through the computer's serial port. I wish we'd used an AOTF instead. These shutters shake the table for a full half-second every time they open or close. We work around this by waiting for the vibration to die before acquisition, but it's annoying.

## Software ##

If you want to use my software to automate data acquisition, you should probably know at least a little Python. My code works, but I'm by no means a professional, and you'll probably want to customize it to some degree.

Our [data-acquisition code](http://code.google.com/p/msim/source/browse/#hg%2Fhardware_control) is written in python, and I never got around to writing a graphical interface. Sorry! We edit and run [sim\_scope.py](http://code.google.com/p/msim/source/browse/hardware_control/sim_scope.py) to acquire data (as Kelsey [describes here](http://code.google.com/p/msim/wiki/Data_Acquisition)), which depends on [pco.py](http://code.google.com/p/msim/source/browse/hardware_control/pco.py) (the camera), [dmd.py](http://code.google.com/p/msim/source/browse/hardware_control/dmd.py) (the DMD), [stage.py](http://code.google.com/p/msim/source/browse/hardware_control/stage.py) (our axial positioner), [shutters.py](http://code.google.com/p/msim/source/browse/hardware_control/shutters.py) (the SH05 shutters), and [wheel.py](http://code.google.com/p/msim/source/browse/hardware_control/wheel.py) (our [FW102C Thorlabs filter wheel](http://www.thorlabs.com/NewGroupPage9.cfm?ObjectGroup_ID=988)). I put a decent amount of effort into sim\_scope.py, dmd.py, and pco.py; the other scripts are just simple serial port commands. I hard-coded which port each one talks to, so you'll probably have to modify that for your system.

If anyone ends up writing a nice graphical interface for this control code, or (better still), porting it over to MicroManager, I'd be eternally grateful.