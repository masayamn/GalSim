import numpy
import sys, os
import math
import logging
import galsim as galsim
import galsim.wfirst as wfirst

def main(argv):
    # Where to find and output data
    path, filename = os.path.split(__file__)
    datapath = os.path.abspath(os.path.join(path, "data/"))
    outpath = os.path.abspath(os.path.join(path, "output/"))	

    # In non-script code, use getLogger(__name__) at module scope instead.
    logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("demo13")

    # initialize (pseudo-)random number generator
    random_seed = 1234567
    rng = galsim.BaseDeviate(random_seed)
    poisson_noise = galsim.PoissonNoise(rng) 

    # read in the WFIRST filters
    filters = wfirst.getBandpasses(AB_zeropoint=True);
    logger.debug('Read in filters')

    # TEMPORARY - filter has redder red limit
    for filter in filters:
        filters[filter].red_limit = 1197.5 

    # read in SEDs
    SED_names = ['CWW_E_ext', 'CWW_Sbc_ext', 'CWW_Scd_ext', 'CWW_Im_ext']
    SEDs = {}
    for SED_name in SED_names:
        SED_filename = os.path.join(datapath, '{0}.sed'.format(SED_name))
        # Here we create some galsim.SED objects to hold star or galaxy spectra.  The most
        # convenient way to create realistic spectra is to read them in from a two-column ASCII
        # file, where the first column is wavelength and the second column is flux. Wavelengths in
        # the example SED files are in Angstroms, flux in flambda.  The default wavelength type for
        # galsim.SED is nanometers, however, so we need to override by specifying
        # `wave_type = 'Ang'`.
        SED = galsim.SED(SED_filename, wave_type='Ang')
        # The normalization of SEDs affects how many photons are eventually drawn into an image.
        # One way to control this normalization is to specify the flux in a given bandpass filter. We pick for example, W149 and enforce the flux through the filter to be of magnitude specified by 'mag_norm'
        bandpass = filters['W149']
        mag_norm = 22.0
        
        # TEMPORARY till the new SEDs are deployed
        print "SED's redlimit = ", SED.red_limit
        bandpass.red_limit = SED.red_limit
        print "Current flux = ", SED.calculateFlux(bandpass=filters['W149'])
        
        SEDs[SED_name] = SED.withMagnitude(target_magnitude=mag_norm, bandpass=filters['W149'])

    logger.debug('Successfully read in SEDs')

    logger.info('')
    logger.info('Simulating a chromatic bulge+disk galaxy')
    redshift = 0.8

    # make a bulge ...
    mono_bulge = galsim.DeVaucouleurs(half_light_radius=0.5)
    bulge_SED = SEDs['CWW_E_ext'].atRedshift(redshift)
    bulge = mono_bulge * bulge_SED
    bulge = bulge.shear(g1=0.12, g2=0.07)
    logger.debug('Created bulge component')
    # ... and a disk ...
    mono_disk = galsim.Exponential(half_light_radius=2.0)
    disk_SED = SEDs['CWW_Im_ext'].atRedshift(redshift)
    disk = mono_disk * disk_SED
    disk = disk.shear(g1=0.4, g2=0.2)
    logger.debug('Created disk component')
    # ... and then combine them.
    bdgal = 0.8*bulge+4*disk

    # Note that at this stage, our galaxy is chromatic but our PSF is still achromatic.  
    logger.debug('Created bulge+disk galaxy final profile')

    # Load WFIRST parameters
    pixel_scale = wfirst.pixel_scale # 0.11 arcseconds
    exptime = wfirst.exptime # 168.1 seconds

    # draw profile through WFIRST filters
    for filter_name, filter_ in filters.iteritems():        
        # Obtaining parameters for Airy PSF
        # TEMPORARY - WFIRST PSF is on it's way
        effective_wavelength = (1e-9)*filters[filter_name].effective_wavelength # now in cm
        effective_diameter = wfirst.diameter*numpy.sqrt(1-wfirst.obscuration**2) 
        lam_over_diam = (1.0*effective_wavelength/wfirst.diameter)*206265.0 # in arcsec      
        PSF = galsim.Airy(obscuration=wfirst.obscuration, lam_over_diam=lam_over_diam)

        #Convolve with PSF
        bdconv = galsim.Convolve([bdgal, PSF])

    	img = galsim.ImageF(512*2,512*2,scale=pixel_scale) # 64, 64
    	bdconv.drawImage(filter_,image=img)

        #Adding sky level to the images. 
        sky_level_pix = wfirst.getSkyLevel(filters[filter_name],exp_time=wfirst.exptime)
        img.array[:,:] += sky_level_pix
        print "sky_level_pix = ", sky_level_pix

        #Adding Poisson Noise       
    	img.addNoise(poisson_noise)

        logger.debug('Created {0}-band image'.format(filter_name))
        out_filename = os.path.join(outpath, 'demo13_{0}.fits'.format(filter_name))
        galsim.fits.write(img,out_filename)
        logger.debug('Wrote {0}-band image to disk'.format(filter_name))

        #print "After adding noise", img.array.min(), img.array.max()

        # Accounting Reciprocity Failure
        # Reciprocity failure is identified as a change in the rate of charge accumulation with photon flux, resulting in loss of sensitivity at low signal levels. This is a non-ideal feature of the detector that is dependent on the charge present at the pixel and the duration of exposure.

        img.addReciprocityFailure(exp_time=exptime,alpha=wfirst.reciprocity_alpha)
        logger.debug('Accounted for Reciprocity Failure in {0}-band image'.format(filter_name))
        out_filename = os.path.join(outpath, 'demo13_RecipFail_{0}.fits'.format(filter_name))
        galsim.fits.write(img,out_filename)
        logger.debug('Wrote {0}-band image  after accounting for Recip. Failure to disk'.format(filter_name))

    	# Applying a quadratic non-linearity
        # In order to convert the units from electrons to ADU, we must multiply the image by a gain factor. The gain has a weak dependency on the charge present in each pixel. This dependency is accounted for by changing the pixel values (in electrons) and applying a constant gain later

    	NLfunc = wfirst.NLfunc
    	img.applyNonlinearity(NLfunc)
    	logger.debug('Applied Nonlinearity to {0}-band image'.format(filter_name))
        out_filename = os.path.join(outpath, 'demo13_NL_{0}.fits'.format(filter_name))
        galsim.fits.write(img,out_filename)
        logger.debug('Wrote {0}-band image with Nonlinearity to disk'.format(filter_name))

        # Adding Interpixel Capacitance

        # Adding Read Noise
    	read_noise = galsim.CCDNoise(rng)
        read_noise.setReadNoise(wfirst.read_noise)
        img.addNoise(read_noise)
        logger.debug('Added Readnoise for {0}-band image'.format(filter_name))
        out_filename = os.path.join(outpath, 'demo13_ReadNoise_{0}.fits'.format(filter_name))
        galsim.fits.write(img,out_filename)
        logger.debug('Wrote {0}-band image after adding readnoise to disk'.format(filter_name))

    logger.info('You can display the output in ds9 with a command line that looks something like:')
    logger.info('ds9 -rgb -blue -scale limits -0.2 0.8 output/demo13_ReadNoise_J129.fits -green -scale limits'
                +' -0.25 1.0 output/demo13_ReadNoise_W149.fits -red -scale limits -0.25 1.0 output/demo13_ReadNoise_Z087.fits'
                +' -zoom 2 &')

if __name__ == "__main__":
	main(sys.argv)

