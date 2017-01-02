# Copyright (c) 2012-2016 by the GalSim developers team on GitHub
# https://github.com/GalSim-developers
#
# This file is part of GalSim: The modular galaxy image simulation toolkit.
# https://github.com/GalSim-developers/GalSim
#
# GalSim is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
#
"""@file lensing_ps.py
The "lensing engine" for drawing shears from some power spectrum.
"""

import galsim
import numpy as np

def theoryToObserved(gamma1, gamma2, kappa):
    """Helper function to convert theoretical lensing quantities to observed ones.

    This helper function is used internally by PowerSpectrum.getShear(), getMagnification(), and
    getLensing() to convert from theoretical quantities (shear and convergence) to observable ones
    (reduced shear and magnification).  Users of PowerSpectrum.buildGrid() outputs can also apply
    this method directly to the outputs in order to get the values of reduced shear and
    magnification on the output grid.

    @param gamma1       The first shear component, which must be the NON-reduced shear.  This and
                        all other inputs should be supplied either as individual floating point
                        numbers, tuples, lists, or NumPy arrays.
    @param gamma2       The second (x) shear component, which must be the NON-reduced shear.
    @param kappa        The convergence.

    @returns the reduced shear and magnification as a tuple `(g1, g2, mu)` where each item has the
             same form as the input gamma1, gamma2, and kappa.
    """
    # check nature of inputs to make sure they are appropriate
    if type(gamma1) != type(gamma2):
        raise ValueError("Input shear components must be of the same type!")
    if type(kappa) != type(gamma1):
        raise ValueError("Input shear and convergence must be of the same type!")
    gamma1_tmp = np.array(gamma1)
    gamma2_tmp = np.array(gamma2)
    kappa_tmp = np.array(kappa)
    if gamma1_tmp.shape != gamma2_tmp.shape:
        raise ValueError("Shear arrays passed to theoryToObserved() do not have the same shape!")
    if kappa_tmp.shape != gamma1_tmp.shape:
        raise ValueError(
           "Convergence and shear arrays passed to theoryToObserved() do not have the same shape!")

    # Now convert to reduced shear and magnification
    g1 = gamma1_tmp/(1.-kappa_tmp)
    g2 = gamma2_tmp/(1.-kappa_tmp)
    mu = 1./((1.-kappa_tmp)**2 - (gamma1_tmp**2 + gamma2_tmp**2))

    # Put back into same format as inputs
    if isinstance(gamma1, float):
        return float(g1), float(g2), float(mu)
    elif isinstance(gamma1, list):
        return list(g1), list(g2), list(mu)
    elif isinstance(gamma1, tuple):
        return tuple(g1), tuple(g2), tuple(mu)
    elif isinstance(gamma1, np.ndarray):
        return g1, g2, mu
    else:
        raise ValueError("Unknown input type for shears, convergences: %s",type(gamma1))

class PowerSpectrum(object):
    """Class to represent a lensing shear field according to some power spectrum P(k).

    General considerations
    ----------------------

    A PowerSpectrum represents some (flat-sky) shear power spectrum, either for gridded points or at
    arbitary positions.  This class is originally initialized with a power spectrum from which we
    would like to generate g1 and g2 (and, optionally, convergence kappa) values.  It generates
    shears on a grid, and if necessary, when getShear() (or another `get` method) is called, it will
    interpolate to the requested positions.  For detail on how these processes are carried out,
    please see the document in the GalSim repository, `devel/modules/lensing_engine.pdf`.

    This class generates the shears according to the input power spectrum using a DFT approach,
    which means that we implicitly assume our discrete representation of P(k) on a grid is one
    complete cell in an infinite periodic series.  We are making assumptions about what P(k) is
    doing outside of our minimum and maximum k range, and those must be kept in mind when comparing
    with theoretical expectations.  Specifically, since the power spectrum is realized on only a
    finite grid it has been been effectively bandpass filtered between a minimum and maximum k value
    in each of the k1, k2 directions.  See the buildGrid() method for more information.

    As a result, the shear generation currently does not include sample variance due to coverage of
    a finite patch.  We explicitly enforce `P(k=0)=0`, which is true for the full sky in a
    reasonable cosmological model, but it ignores the fact that our little patch of sky might
    reasonably live in some special region with respect to shear correlations.  Our `P(k=0)=0` is
    essentially setting the integrated power below our minimum k value to zero.  The implications of
    the discrete representation, and the `P(k=0)=0` choice, are discussed in more detail in
    `devel/modules/lensing_engine.pdf`.

    The effective shear correlation function for the gridded points will be modified both because of
    the DFT approach to representing shears according to a power spectrum, and because of the power
    cutoff below and above the minimum k values.  The latter effect can be particularly important on
    large scales, so the buildGrid() method has some keywords that can be used to reduce the
    impact of the minimum k set by the grid extent.  The calculateXi() method can be used to
    calculate the expected shear correlation functions given the minimum and maximum k for some grid
    (but ignoring the discrete vs. continuous Fourier transform effects), for comparison with some
    ideal theoretical correlation function given an infinite k range.

    When interpolating the shears to non-gridded points, the shear correlation function and power
    spectrum are modified; see the getShear() and other `get` method docstrings for more details.

    The power spectra to be used
    ----------------------------

    When creating a PowerSpectrum instance, you must specify at least one of the E or B mode power
    spectra, which is normally given as a function P(k).  The typical thing is to just use a lambda
    function in Python (i.e., a function that is not associated with a name); for example, to define
    P(k)=k^2, one would use `lambda k : k**2`.  But the power spectra can also be more complicated
    user-defined functions that take a single argument `k` and return the power at that `k` value,
    or they can be instances of the LookupTable class for power spectra that are known at
    particular `k` values but for which there is not a simple analytic form.

    Cosmologists often express the power spectra in terms of an expansion in spherical harmonics
    (ell), i.e., the C_ell values.  In the flat-sky limit, we can replace ell with k and C_ell with
    P(k).  Thus, k and P(k) have dimensions of inverse angle and angle^2, respectively.  It is quite
    common for people to plot ell(ell+1)C_ell/2pi, a dimensionless quantity; the analogous flat-sky
    quantity is Delta^2 = k^2 P(k)/2pi.  By default, the PowerSpectrum object assumes it is getting
    P(k), but it is possible to instead give it Delta^2 by setting the optional keyword `delta2 =
    True` in the constructor.

    The power functions must return a list/array that is the same size as what they are given, e.g.,
    in the case of no power or constant power, a function that just returns a float would not be
    permitted; it would have to return an array of floats all with the same value.

    It is important to note that the power spectra used to initialize the PowerSpectrum object
    should use the same units for k and P(k), i.e., if k is in inverse radians then P(k) should be
    in radians^2 (as is natural for outputs from a cosmological shear power spectrum calculator).
    However, when we actually draw images, there is a natural scale that defines the pitch of the
    image, which is typically taken to be arcsec.  This definition of a specific length scale
    means that by default we assume all quantities to the PowerSpectrum are in arcsec, and those are
    the units used for internal calculations, but the `units` keyword can be used to specify
    different input units for P(k) (again, within the constraint that k and P(k) must be
    consistent).  If the `delta2` keyword is set to specify that the input is actually the
    dimensionless power Delta^2, then the input `units` are taken to apply only to the k values.

    @param e_power_function A function or other callable that accepts a NumPy array of |k| values,
                            and returns the E-mode power spectrum P_E(|k|) in an array of the same
                            shape.  The function should return the power spectrum desired in the E
                            (gradient) mode of the image.
                            It may also be a string that can be converted to a function using
                            `eval('lambda k : '+e_power_function)`, a LookupTable, or `file_name`
                            from which to read in a LookupTable.  If a `file_name` is given, the
                            resulting LookupTable uses the defaults for the LookupTable class,
                            namely spline interpolation in P(k).  Users who wish to deviate from
                            those defaults (for example, to interpolate in log(P) and log(k), as
                            might be more natural for power-law functions) should instead read in
                            the file to create a LookupTable using the necessary non-default
                            settings. [default: None, which means no E-mode power.]
    @param b_power_function A function or other callable that accepts a NumPy array of |k| values,
                            and returns the B-mode power spectrum P_B(|k|) in an array of the same
                            shape.  The function should return the power spectrum desired in the B
                            (curl) mode of the image.  See description of `e_power_function` for
                            input format options.
                            [default: None, which means no B-mode power.]
    @param delta2           Is the power actually given as dimensionless Delta^2, which requires us
                            to multiply by 2pi / k^2 to get the shear power P(k) in units of
                            angle^2?  [default: False]
    @param units            The angular units used for the power spectrum (i.e. the units of
                            k^-1 and sqrt(P)). This should be either an AngleUnit instance
                            (e.g. galsim.radians) or a string (e.g. 'radians'). [default: arcsec]
    """
    _req_params = {}
    _opt_params = { 'e_power_function' : str, 'b_power_function' : str,
                    'delta2' : bool, 'units' : str }
    _single_params = []
    _takes_rng = False

    def __init__(self, e_power_function=None, b_power_function=None, delta2=False,
                 units=galsim.arcsec):
        # Check that at least one power function is not None
        if e_power_function is None and b_power_function is None:
            raise AttributeError(
                "At least one of e_power_function or b_power_function must be provided.")

        self.e_power_function = e_power_function
        self.b_power_function = b_power_function
        self.delta2 = delta2
        self.units = units

        # Try these conversions, but we don't actually keep the output.  This just
        # provides a way to test if the arguments are sane.
        # Note: we redo this in buildGrid for real rather than keeping the outputs
        # (e.g. in self.e_power_function, self.b_power_function) so that PowerSpectrum is
        # picklable.  It turns out lambda functions are not picklable.
        self._convert_power_function(self.e_power_function,'e_power_function')
        self._convert_power_function(self.b_power_function,'b_power_function')

        # Check validity of units
        if isinstance(units, str):
            # if the string is invalid, this raises a reasonable error message.
            units = galsim.angle.get_angle_unit(units)
        if not isinstance(units, galsim.AngleUnit):
            raise ValueError("units must be either an AngleUnit or a string")

        if units == galsim.arcsec:
            self.scale = 1
        else:
            self.scale = 1. * units / galsim.arcsec

    def __repr__(self):
        s = 'galsim.PowerSpectrum(e_power_function=%r'%self.e_power_function
        if self.b_power_function is not None:
            s += ', b_power_function=%r'%self.b_power_function
        if self.delta2:
            s += ', delta2=%r'%self.delta2
        if self.units != galsim.arcsec:
            s += ', units=%r'%self.units
        s += ')'
        return s

    def __str__(self):
        s = 'galsim.PowerSpectrum(e_power_function=%s'%self.e_power_function
        if self.b_power_function is not None:
            s += ', b_power_function=%s'%self.b_power_function
        s += ')'
        return s

    def __eq__(self, other):
        return (isinstance(other, PowerSpectrum) and
                self.e_power_function == other.e_power_function and
                self.b_power_function == other.b_power_function and
                self.delta2 == other.delta2 and
                self.scale == other.scale)
    def __ne__(self, other): return not self.__eq__(other)

    def __hash__(self): return hash(repr(self))

    def buildGrid(self, grid_spacing=None, ngrid=None, rng=None, interpolant=None,
                  center=galsim.PositionD(0,0), units=galsim.arcsec, get_convergence=False,
                  kmax_factor=1, kmin_factor=1, bandlimit="hard"):
        """Generate a realization of the current power spectrum on the specified grid.

        Basic functionality
        -------------------

        This function will generate a Gaussian random realization of the specified E and B mode
        shear power spectra at a grid of positions, specified by the input parameters `grid_spacing`
        (distance between grid points) and `ngrid` (number of grid points in each direction.)  Units
        for `grid_spacing` and `center` can be specified using the `units` keyword; the default is
        arcsec, which is how all values are stored internally.  It automatically computes and stores
        grids for the shears and convergence.  However, since many users are primarily concerned
        with shape distortion due to shear, the default is to return only the shear components; the
        `get_convergence` keyword can be used to also return the convergence.

        The quantities that are returned are the theoretical shears and convergences, usually
        denoted gamma and kappa, respectively.  Users who wish to obtain the more
        observationally-relevant reduced shear and magnification (that describe real lensing
        distortions) can either use the getShear(), getMagnification(), or getLensing() methods
        after buildGrid(), or can use the convenience function galsim.lensing_ps.theoryToObserved()
        to convert from theoretical to observed quantities.

        Effects of DFT approach, and keywords that can be used to ameliorate them
        -------------------------------------------------------------------------

        Note that the shears generated using this method correspond to the PowerSpectrum multiplied
        by a sharp bandpass filter, set by the dimensions of the grid.

        The filter sets `P(k)` = 0 for

            |k1|, |k2| < kmin / 2

        and
            |k1|, |k2| > kmax + kmin / 2

        where
            kmin = 2. * pi / (ngrid * grid_spacing)
            kmax = pi / grid_spacing

        and where we have adopted the convention that grid points at a given `k` represent the
        interval between (k - dk/2) and (k + dk/2) (noting that the grid spacing dk in k space
        is equivalent to `kmin`).

        It is worth remembering that this bandpass filter will *not* look like a circular annulus
        in 2D `k` space, but is rather more like a thick-sided picture frame, having a small square
        central cutout of dimensions `kmin` by `kmin`.  These properties are visible in the shears
        generated by this method.

        If you care about these effects and want to ameliorate their effect, there are two
        optional kwargs you can provide: `kmin_factor` and `kmax_factor`, both of which are 1
        by default.  These should be integers >= 1 that specify some factor smaller or larger
        (for kmin and kmax respectively) you want the code to use for the underlying grid in
        fourier space.  The final shear grid is returned using the specified `ngrid` and
        `grid_spacing` parameters.  But the intermediate grid in Fourier space will be larger
        by the specified factors.

        Note: These are really just for convenience, since you could easily get the same effect
        by providing different values of ngrid and grid_spacing and then take a subset of them.
        The `kmin_factor` and `kmax_factor` just handle the scalings appropriately for you.

        Use of `kmin_factor` and `kmax_factor` should depend on the desired application.  For
        accurate representation of power spectra, one should not change these values from their
        defaults of 1.  Changing them from one means the E- and B-mode power spectra that are input
        will be valid for the larger intermediate grids that get generated in Fourier space, but not
        necessarily for the smaller ones that get returned to the user.  However, for accurate
        representation of cosmological shear correlation functions, use of `kmin_factor` larger than
        one can be helpful in getting the shear correlations closer to the ideal theoretical ones
        (see `devel/module/lensing_engine.pdf` for details).

        Aliasing
        --------

        If the user provides a power spectrum that does not include a cutoff at kmax, then our
        method of generating shears will result in aliasing that will show up in both E- and
        B-modes.  Thus the buildGrid() method accepts an optional keyword argument called
        `bandlimit` that can tell the PowerSpectrum object to cut off power above kmax
        automatically, where the relevant kmax is larger than the grid Nyquist frequency by a factor
        of `kmax_factor`.  The allowed values for `bandlimit` are None (i.e., do nothing), `hard`
        (set power to zero above the band limit), or `soft` (use an arctan-based softening function
        to make the power go gradually to zero above the band limit).  By default, `bandlimit=hard`.
        Use of this keyword does nothing to the internal representation of the power spectrum, so if
        the user calls the buildGrid() method again, they will need to set `bandlimit` again (and if
        their grid setup is different in a way that changes `kmax`, then that's fine).

        Interpolation
        -------------

        If the grid is being created for the purpose of later interpolating to random positions, the
        following findings should be kept in mind: since the interpolant modifies the effective
        shear correlation function on scales comparable to <~3x the grid spacing, the grid spacing
        should be chosen to be at least 3 times smaller than the minimum scales on which the user
        wishes to reproduce the shear correlation function accurately.  Ideally, the grid should be
        somewhat larger than the region in which shears at random points are needed, so that edge
        effects in the interpolation will not be important.  For this purpose, there should be >~5
        grid points outside of the region in which interpolation will take place.  Ignoring this
        edge effect and using the grid for interpolation out to its edges can suppress shear
        correlations on all scales by an amount that depends on the grid size; for a 100x100 grid,
        the suppression is ~2-3%.  Note that the above numbers came from tests that use a
        cosmological shear power spectrum; precise figures for this suppression can also depend on
        the shear correlation function itself.

        Sign conventions and other info
        -------------------------------

        Note also that the convention for axis orientation differs from that for the GREAT10
        challenge, so when using codes that deal with GREAT10 challenge outputs, the sign of our g2
        shear component must be flipped.

        For more information on the effects of finite grid representation of the power spectrum
        see `devel/modules/lensing_engine.pdf`.

        Some examples:

        1. Get shears on a grid of points separated by 1 arcsec:

                >>> my_ps = galsim.PowerSpectrum(lambda k : k**2)
                >>> g1, g2 = my_ps.buildGrid(grid_spacing = 1., ngrid = 100)

           The returned g1, g2 are 2-d NumPy arrays of values, corresponding to the values of
           g1 and g2 at the locations of the grid points.

           For a given value of `grid_spacing` and `ngrid`, we could get the x and y values on the
           grid using

                >>> import numpy as np
                >>> min = (-ngrid/2 + 0.5) * grid_spacing
                >>> max = (ngrid/2 - 0.5) * grid_spacing
                >>> x, y = np.meshgrid(np.arange(min,max+grid_spacing,grid_spacing),
                ...                    np.arange(min,max+grid_spacing,grid_spacing))

           where the center of the grid is taken to be (0,0).

        2. Rebuild the grid using a particular rng and set the location of the center of the grid
           to be something other than the default (0,0)

                >>> g1, g2 = my_ps.buildGrid(grid_spacing = 8., ngrid = 65,
                ...                          rng = galsim.BaseDeviate(1413231),
                ...                          center = (256.5, 256.5) )

        3. Make a PowerSpectrum from a tabulated P(k) that gets interpolated to find the power at
           all necessary values of k, then generate shears and convergences on a grid, and convert
           to reduced shear and magnification so they can be used to transform galaxy images.
           Assuming that k and P_k are either lists, tuples, or 1d NumPy arrays containing k and
           P(k):

                >>> tab_pk = galsim.LookupTable(k, P_k)
                >>> my_ps = galsim.PowerSpectrum(tab_pk)
                >>> g1, g2, kappa = my_ps.buildGrid(grid_spacing = 1., ngrid = 100,
                ...                                 get_convergence = True)
                >>> g1_r, g2_r, mu = galsim.lensing_ps.theoryToObserved(g1, g2, kappa)

        @param grid_spacing     Spacing for an evenly spaced grid of points, by default in arcsec
                                for consistency with the natural length scale of images created
                                using the drawImage() method.  Other units can be specified using
                                the `units` keyword.
        @param ngrid            Number of grid points in each dimension.  [Must be an integer]
        @param rng              A BaseDeviate object for drawing the random numbers. [default: None]
        @param interpolant      Interpolant that will be used for interpolating the gridded shears
                                by methods like getShear(), getConvergence(), etc. if they are
                                later called. [default: galsim.Lanczos(5)]
        @param center           If setting up a new grid, define what position you want to consider
                                the center of that grid.  Units must be consistent with those for
                                `grid_spacing`.  [default: galsim.PositionD(0,0)]
        @param units            The angular units used for the positions.  [default: arcsec]
        @param get_convergence  Return the convergence in addition to the shear?  Regardless of the
                                value of `get_convergence`, the convergence will still be computed
                                and stored for future use. [default: False]
        @param kmin_factor      Factor by which the grid spacing in fourier space is smaller than
                                the default.  i.e.
                                    kmin = 2. * pi / (ngrid * grid_spacing) / kmin_factor
                                [default: 1; must be an integer]
        @param kmax_factor      Factor by which the overall grid in fourier space is larger than
                                the default.  i.e.
                                    kmax = pi / grid_spacing * kmax_factor
                                [default: 1; must be an integer]
        @param bandlimit        Keyword determining how to handle power P(k) above the limiting k
                                value, kmax.  The options None, 'hard', and 'soft' correspond to
                                doing nothing (i.e., allow P(>kmax) to be aliased to lower k
                                values), cutting off all power above kmax, and applying a softening
                                filter to gradually cut off power above kmax.  Use of this keyword
                                does not modify the internally-stored power spectrum, just the
                                shears generated for this particular call to buildGrid().
                                [default: "hard"]

        @returns the tuple (g1,g2[,kappa]), where each is a 2-d NumPy array and kappa is included
                 iff `get_convergence` is set to True.
        """
        # Check problem cases for regular grid of points
        if grid_spacing is None or ngrid is None:
            raise ValueError("Both a spacing and a size are required for buildGrid.")
        # Check for validity of integer values
        if not isinstance(ngrid, int):
            if ngrid != int(ngrid):
                raise ValueError("ngrid must be an integer")
            ngrid = int(ngrid)
        if not isinstance(kmin_factor, int):
            if kmin_factor != int(kmin_factor):
                raise ValueError("kmin_factor must be an integer")
            kmin_factor = int(kmin_factor)
        if not isinstance(kmax_factor, int):
            if kmax_factor != int(kmax_factor):
                raise ValueError("kmax_factor must be an integer")
            kmax_factor = int(kmax_factor)

        # Check if center is a Position
        if isinstance(center,galsim.PositionD):
            pass  # This is what it should be
        elif isinstance(center,galsim.PositionI):
            # Convert to a PositionD
            center = galsim.PositionD(center.x, center.y)
        elif isinstance(center, tuple) and len(center) == 2:
            # Convert (x,y) tuple to PositionD
            center = galsim.PositionD(center[0], center[1])
        else:
            raise TypeError("Unable to parse the input center argument for buildGrid")

        # Automatically convert units to arcsec at the outset, then forget about it.  This is
        # because PowerSpectrum by default wants to work in arsec, and all power functions are
        # automatically converted to do so, so we'll also do that here.
        if isinstance(units, str):
            # if the string is invalid, this raises a reasonable error message.
            units = galsim.angle.get_angle_unit(units)
        if not isinstance(units, galsim.AngleUnit):
            raise ValueError("units must be either an AngleUnit or a string")
        if units != galsim.arcsec:
            scale_fac = (1.*units) / galsim.arcsec
            center *= scale_fac
            grid_spacing *= scale_fac

        # The final grid spacing that will be in the computed images is grid_spacing/kmax_factor.
        self.grid_spacing = grid_spacing // kmax_factor
        self.center = center

        # We have to make an adjustment to the center value to account for how the xValue function
        # of SBInterpolatedImage works.  xValue(0,0) gives the image value at the _nominal_
        # image center.  i.e. the location you get from im.center().  However, for even-sized
        # images, this isn't the true center, since it is constrained to be a PositionI,
        # and the true center is halfway between two pixels.
        # Therefore, we would want an input position of center to use xValue(-0.5, -0.5) in that
        # case.  Or, equivalently, we want an input position of center + (0.5,0.5)*grid_spacing
        # to use xValue(0,0).
        if ngrid % 2 == 0:
            self.center += galsim.PositionD(0.5,0.5) * self.grid_spacing
            self.adjust_center = True
        else:
            self.adjust_center = False

        # It is also convenient to store the bounds within which an input position is allowed.
        self.bounds = galsim.BoundsD( center.x - ngrid * grid_spacing / 2. ,
                                      center.x + ngrid * grid_spacing / 2. ,
                                      center.y - ngrid * grid_spacing / 2. ,
                                      center.y + ngrid * grid_spacing / 2. )
        # Expand the bounds slightly to make sure rounding errors don't lead to points on the
        # edge being considered off the edge.
        self.bounds = self.bounds.expand( 1. + 1.e-15 )

        gd = galsim.GaussianDeviate(rng)

        # Check that the interpolant is valid.
        if interpolant is None:
            self.interpolant = galsim.Lanczos(5)
        else:
            self.interpolant = galsim.utilities.convert_interpolant(interpolant)

        # Convert power_functions into callables:
        e_power_function = self._convert_power_function(self.e_power_function,'e_power_function')
        b_power_function = self._convert_power_function(self.b_power_function,'b_power_function')

        # Figure out how to apply band limit if requested.
        # Start by calculating kmax in the appropriate units:
        # Generally, it should be kmax_factor*pi/(input grid spacing).  We have already converted
        # the user-input grid spacing to arcsec, the units that the PowerSpectrum class uses
        # internally, and divided it by kmax_factor to get self.grid_spacing, so here we just use
        # pi/self.grid_spacing.
        k_max = np.pi / self.grid_spacing
        if bandlimit == 'hard':
            def bandlimit_func(k, k_max):
                return self._hard_cutoff(k, k_max)
        elif bandlimit == 'soft':
            def bandlimit_func(k, k_max):
                return self._softening_function(k, k_max)
        elif bandlimit is None:
            def bandlimit_func(k, k_max):
                return 1.0
        else:
            raise RuntimeError("Unrecognized option for band limit!")

        # If we actually have dimensionless Delta^2, then we must convert to power
        # P(k) = 2pi Delta^2 / k^2,
        # which has dimensions of angle^2.
        if e_power_function is None:
            p_E = None
        elif self.delta2:
            # Here we have to go from Delta^2 (dimensionless) to P = 2pi Delta^2 / k^2.  We want to
            # have P and therefore 1/k^2 in units of arcsec, so we won't rescale the k that goes in
            # the denominator.  This naturally gives P(k) in arcsec^2.
            p_E = lambda k : (2.*np.pi) * e_power_function(self.scale*k)/(k**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        elif self.scale != 1:
            # Here, the scale comes in two places:
            # The units of k have to be converted from 1/arcsec, which GalSim wants to use, into
            # whatever the power spectrum function was defined to use.
            # The units of power have to be converted from (input units)^2 as returned by the power
            # function, to Galsim's units of arcsec^2.
            # Recall that scale is (input units)/arcsec.
            p_E = lambda k : e_power_function(self.scale*k)*(self.scale**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        else:
            p_E = lambda k : e_power_function(k) * bandlimit_func(k, k_max)

        if b_power_function is None:
            p_B = None
        elif self.delta2:
            p_B = lambda k : (2.*np.pi) * b_power_function(self.scale*k)/(k**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        elif self.scale != 1:
            p_B = lambda k : b_power_function(self.scale*k)*(self.scale**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        else:
            p_B = lambda k : b_power_function(k) * bandlimit_func(k, k_max)

        # Build the grid
        self.ngrid_tot = ngrid * kmin_factor * kmax_factor
        self.pixel_size = grid_spacing/kmax_factor
        psr = PowerSpectrumRealizer(self.ngrid_tot, self.pixel_size, p_E, p_B)
        self.grid_g1, self.grid_g2, self.grid_kappa = psr(gd)
        if kmin_factor != 1 or kmax_factor != 1:
            # Need to make sure the rows are contiguous so we can use it in the constructor
            # of the ImageD objects below.  This requires a copy.
            s = slice(0,ngrid*kmax_factor,kmax_factor)
            self.grid_g1 = np.array(self.grid_g1[s,s], copy=True, order='C')
            self.grid_g2 = np.array(self.grid_g2[s,s], copy=True, order='C')
            self.grid_kappa = np.array(self.grid_kappa[s,s], copy=True, order='C')

        # Set up the images to be interpolated.
        # Note: We don't make the SBInterpolatedImages yet, since it's not picklable.
        #       So we wait to create them when we are actually going to use them.
        self.im_g1 = galsim.ImageD(self.grid_g1)
        self.im_g2 = galsim.ImageD(self.grid_g2)
        self.im_kappa = galsim.ImageD(self.grid_kappa)

        if get_convergence:
            return self.grid_g1, self.grid_g2, self.grid_kappa
        else:
            return self.grid_g1, self.grid_g2

    def nRandCallsForBuildGrid(self):
        """Return the number of times the rng() was called the last time buildGrid was called.

        This can be useful for keeping rngs in sync if the connection between them is broken
        (e.g. when calling the function through a Proxy object).
        """
        if not hasattr(self,'ngrid_tot'):
            raise RuntimeError("BuildGrid has not been called yet.")
        ntot = 0
        # cf. PowerSpectrumRealizer._generate_power_array
        temp = 2 * np.product( (self.ngrid_tot, self.ngrid_tot//2 +1 ) )
        if self.e_power_function is not None:
            ntot += temp
        if self.b_power_function is not None:
            ntot += temp
        return int(ntot)

    def subsampleGrid(self, subsample_fac, get_convergence=False):
        """Routine to use a regular subset of the grid points without a completely new call to
        buildGrid().

        This routine can be used after buildGrid(), in order to use a subset of the grid points
        corresponding to every Nth point along both dimensions.  All internally-stored parameters
        such as the shear and convergence values, the grid spacing, etc. get properly updated.

        @param subsample_fac      Factor by which to subsample the gridded shear and convergence
                                  fields.  This is currently required to be a factor of `ngrid`.
        @param get_convergence    Return the convergence in addition to the shear?  Regardless of
                                  the value of `get_convergence`, the convergence will still be
                                  computed and stored for future use. [default: `False`]
        """
        # Check that buildGrid has already been called.
        if not hasattr(self, 'im_g1'):
            raise RuntimeError("PowerSpectrum.buildGrid must be called before subsampleGrid")

        # Check that subsample_fac is a factor of ngrid.
        effective_ngrid = self.im_g1.array.shape[0]
        if (not isinstance(subsample_fac,int)
            or effective_ngrid%subsample_fac!=0
            or subsample_fac<=1):
            raise RuntimeError("Subsample factor must be an integer>1 that divides the grid size!")

        # Make new array subsamples and turn them into Images
        self.im_g1 = galsim.ImageD(
            np.ascontiguousarray(self.im_g1.array[::subsample_fac,::subsample_fac]))
        self.im_g2 = galsim.ImageD(
            np.ascontiguousarray(self.im_g2.array[::subsample_fac,::subsample_fac]))
        self.im_kappa = galsim.ImageD(
            np.ascontiguousarray(self.im_kappa.array[::subsample_fac,::subsample_fac]))

        # Update internal parameters: grid_spacing, center.
        if self.adjust_center:
            self.center += galsim.PositionD(0.5,0.5) * self.grid_spacing * (subsample_fac-1)
        self.grid_spacing *= subsample_fac

        if get_convergence:
            return self.grid_g1, self.grid_g2, self.grid_kappa
        else:
            return self.grid_g1, self.grid_g2

    def _convert_power_function(self, pf, pf_str):
        if pf is None: return None

        # Convert string inputs to either a lambda function or LookupTable
        if isinstance(pf,str):
            import os
            if os.path.isfile(pf):
                pf = galsim.LookupTable(file=pf)
            else:
                # Detect at least _some_ forms of malformed string input.  Note that this
                # test assumes that the eval string completion is defined for k=1.0.
                try:
                    pf = galsim.utilities.math_eval('lambda k : ' + pf)
                    pf(1.0)
                except Exception as e:
                    raise ValueError(
                        "String power_spectrum must either be a valid filename or something that "+
                        "can eval to a function of k.\n"+
                        "Input provided: {0}\n".format(origpf)+
                        "Caught error: {0}".format(e))


        # Check that the function is sane.
        # Note: Only try tests below if it's not a LookupTable.
        #       (If it's a LookupTable, then it could be a valid function that isn't
        #        defined at k=1, and by definition it must return something that is the
        #        same length as the input.)
        if not isinstance(pf, galsim.LookupTable):
            f1 = pf(np.array((0.1,1.)))
            fake_arr = np.zeros(2)
            fake_p = pf(fake_arr)
            if isinstance(fake_p, float):
                raise AttributeError(
                    "Power function MUST return a list/array same length as input")
        return pf

    def calculateXi(self, grid_spacing, ngrid, kmax_factor=1, kmin_factor=1, n_theta=100,
                    units=galsim.arcsec, bandlimit="hard"):
        """Calculate shear correlation functions for the current power spectrum on the specified
        grid.

        This function will calculate the theoretical shear correlation functions, xi_+ and xi_-, for
        this power spectrum and the grid configuration specified using keyword arguments, taking
        into account the minimum and maximum k range implied by the grid parameters, `kmin_factor`,
        and `kmax_factor`.  Most theoretical correlation function calculators assume an infinite k
        range, so this utility can be used to check how close the chosen grid parameters (and the
        implied minimum and maximum k) come to the "ideal" result.  This is particularly useful on
        large scales, since in practice the finite grid extent limits the minimum k value and
        therefore can suppress shear correlations on large scales.  Note that the actual shear
        correlation function in the generated shears will still differ from the one calculated here
        due to differences between the discrete and continuous Fourier transform.

        The quantities that are returned are three NumPy arrays: separation theta (in the adopted
        units), xi_+, and xi_-.  These are defined in terms of the E- and B-mode shear power
        spectrum as in the document `devel/modules/lensing_engine.pdf`, equations 2 and 3.  The
        values that are returned are for a particular theta value, not an average over a range of
        theta values in some bin of finite width.

        This method has been tested with cosmological shear power spectra; users should check for
        sanity of outputs if attempting to use power spectra that have very different scalings with
        k.

        @param grid_spacing     Spacing for an evenly spaced grid of points, by default in arcsec
                                for consistency with the natural length scale of images created
                                using the drawImage() method.  Other units can be specified using
                                the `units` keyword.
        @param ngrid            Number of grid points in each dimension.  [Must be an integer]
        @param units            The angular units used for the positions.  [default = arcsec]
        @param kmin_factor      (Optional) Factor by which the grid spacing in fourier space is
                                smaller than the default.  i.e.
                                    kmin = 2. * pi / (ngrid * grid_spacing) / kmin_factor
                                [default `kmin_factor = 1`; must be an integer]
        @param kmax_factor      (Optional) Factor by which the overall grid in fourier space is
                                larger than the default.  i.e.
                                    kmax = pi / grid_spacing * kmax_factor
                                [default `kmax_factor = 1`; must be an integer]
        @param n_theta          (Optional) Number of logarithmically spaced bins in angular
                                separation. [default `n_theta=100`]
        @param bandlimit        (Optional) Keyword determining how to handle power P(k) above the
                                limiting k value, kmax.  The options None, 'hard', and 'soft'
                                correspond to doing nothing (i.e., allow P(>kmax) to be aliased to
                                lower k values), cutting off all power above kmax, and applying a
                                softening filter to gradually cut off power above kmax.  Use of this
                                keyword does not modify the internally-stored power spectrum, just
                                the result generated by this particular call to `calculateXi`.
                                [default `bandlimit="hard"`]

        @returns the tuple (theta, xi_p, xi_m), 1-d NumPy arrays for the angular separation theta
                 and the two shear correlation functions.
        """
        # Check for validity of integer values
        if not isinstance(ngrid, int):
            if ngrid != int(ngrid):
                raise ValueError("ngrid must be an integer")
            ngrid = int(ngrid)
        if not isinstance(kmin_factor, int):
            if kmin_factor != int(kmin_factor):
                raise ValueError("kmin_factor must be an integer")
            kmin_factor = int(kmin_factor)
        if not isinstance(kmax_factor, int):
            if kmax_factor != int(kmax_factor):
                raise ValueError("kmax_factor must be an integer")
            kmax_factor = int(kmax_factor)
        if not isinstance(n_theta, int):
            if n_theta != int(n_theta):
                raise ValueError("n_theta must be an integer")
            n_theta = int(n_theta)

        # Automatically convert units to arcsec at the outset, then forget about it.  This is
        # because PowerSpectrum by default wants to work in arsec, and all power functions are
        # automatically converted to do so, so we'll also do that here.
        if isinstance(units, str):
            # if the string is invalid, this raises a reasonable error message.
            units = galsim.angle.get_angle_unit(units)
        if not isinstance(units, galsim.AngleUnit):
            raise ValueError("units must be either an AngleUnit or a string")
        if units != galsim.arcsec:
            scale_fac = (1.*units) / galsim.arcsec
            grid_spacing *= scale_fac
        else:
            scale_fac = 1.

        # Decide on a grid of separation values.  Do this in arcsec, for consistency with the
        # internals of the PowerSpectrum class.
        min_sep = grid_spacing
        max_sep = ngrid*grid_spacing
        theta = np.logspace(np.log10(min_sep), np.log10(max_sep), n_theta)

        # Set up the power spectrum to use for the calculations, just as in buildGrid.
        # Convert power_functions into callables:
        e_power_function = self._convert_power_function(self.e_power_function,'e_power_function')
        b_power_function = self._convert_power_function(self.b_power_function,'b_power_function')

        # Apply band limit if requested; see comments in 'buildGrid()' for more details.
        k_max = kmax_factor * np.pi / grid_spacing
        if bandlimit == 'hard':
            def bandlimit_func(k, k_max):
                return self._hard_cutoff(k, k_max)
        elif bandlimit == 'soft':
            def bandlimit_func(k, k_max):
                return self._softening_function(k, k_max)
        elif bandlimit is None:
            def bandlimit_func(k, k_max):
                return 1.0
        else:
            raise RuntimeError("Unrecognized option for band limit!")

        # If we actually have dimensionless Delta^2, then we must convert to power
        # P(k) = 2pi Delta^2 / k^2,
        # which has dimensions of angle^2.
        if e_power_function is None:
            p_E = None
        elif self.delta2:
            # Here we have to go from Delta^2 (dimensionless) to P = 2pi Delta^2 / k^2.  We want to
            # have P and therefore 1/k^2 in units of arcsec, so we won't rescale the k that goes in
            # the denominator.  This naturally gives P(k) in arcsec^2.
            p_E = lambda k : (2.*np.pi) * e_power_function(self.scale*k)/(k**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        elif self.scale != 1:
            # Here, the scale comes in two places:
            # The units of k have to be converted from 1/arcsec, which GalSim wants to use, into
            # whatever the power spectrum function was defined to use.
            # The units of power have to be converted from (input units)^2 as returned by the power
            # function, to Galsim's units of arcsec^2.
            # Recall that scale is (input units)/arcsec.
            p_E = lambda k : e_power_function(self.scale*k)*(self.scale**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        else:
            p_E = lambda k : e_power_function(k) * bandlimit_func(k, k_max)

        if b_power_function is None:
            p_B = None
        elif self.delta2:
            p_B = lambda k : (2.*np.pi) * b_power_function(self.scale*k)/(k**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        elif self.scale != 1:
            p_B = lambda k : b_power_function(self.scale*k)*(self.scale**2) * \
                bandlimit_func(self.scale*k, self.scale*k_max)
        else:
            p_B = lambda k : b_power_function(k) * bandlimit_func(k, k_max)

        # Get k_min value in arcsec:
        k_min = 2.*np.pi / (ngrid * grid_spacing * kmin_factor)

        # Do the actual integration for each of the separation values, now that we have power
        # spectrum functions p_E and p_B.
        xi_p = np.zeros(n_theta)
        xi_m = np.zeros(n_theta)
        for i_theta in range(n_theta):
            # Usually theory calculations use radians.  However, our k and P are already set up to
            # use arcsec, so we need theta to be in arcsec (which it already is) in order for the
            # units to work out right.
            # xi_p = (1/2pi) \int (P_E + P_B) J_0(k theta) k dk
            # xi_m = (1/2pi) \int (P_E - P_B) J_4(k theta) k dk
            if p_E is not None and p_B is not None:
                integrand_p = xip_integrand(p_E + p_B, theta[i_theta])
                integrand_m = xim_integrand(p_E - p_B, theta[i_theta])
            elif p_E is not None:
                integrand_p = xip_integrand(p_E, theta[i_theta])
                integrand_m = xim_integrand(p_E, theta[i_theta])
            else:
                integrand_p = xip_integrand(p_B, theta[i_theta])
                integrand_m = xim_integrand(-p_B, theta[i_theta])
            xi_p[i_theta] = galsim.integ.int1d(integrand_p, k_min, k_max, rel_err=1.e-6,
                                               abs_err=1.e-12)
            xi_m[i_theta] = galsim.integ.int1d(integrand_m, k_min, k_max, rel_err=1.e-6,
                                               abs_err=1.e-12)
        xi_p /= (2.*np.pi)
        xi_m /= (2.*np.pi)

        # Now convert the array of separation values back to whatever units were used as inputs to
        # this function.
        theta /= scale_fac

        # Return arrays with results.
        return theta, xi_p, xi_m

    def _softening_function(self, k, k_max):
        """Softening function for the power spectrum band-limiting step, instead of a hard cut in k.

        We use an arctan function to go smoothly from 1 to 0 above `k_max`.  The input `k` values
        can be in any units, as long as the choice of units for `k` and `k_max` is the same.

        @param k       Fourier wavenumber k.
        @param k_max   Fourier wavenumber for the maximum k value.
        """
        # The magic numbers in the code below come from the following:
        # We define the function as
        #     (arctan[A log(k/k_max) + B] + pi/2)/pi
        # For our current purposes, we will define A and B by requiring that this function go to
        # 0.95 (0.05) for k/k_max = 0.95 (1).  This gives two equations:
        #     0.95 = (arctan[log(0.95) A + B] + pi/2)/pi
        #     0.05 = (arctan[B] + pi/2)/pi.
        # We will solve the second equation:
        #     -0.45 pi = arctan(B), or
        #     B = tan(-0.45 pi).
        b = np.tan(-0.45*np.pi)
        # Then, we get A from the first equation:
        #     0.45 pi = arctan[log(0.95) A + B]
        #     tan(0.45 pi) = log(0.95) A  + B
        a = (np.tan(0.45*np.pi)-b) / np.log(0.95)
        return (np.arctan(a*np.log(k/k_max)+b) + np.pi/2.)/np.pi

    def _hard_cutoff(self, k, k_max):
        if isinstance(k, float):
            return float(k < k_max)
        elif isinstance(k, list) or isinstance(k, tuple):
            return (np.array(k) < k_max).astype(float)
        else: return (k < k_max).astype(float)

    def _wrap_image(self, im, border=7):
        """
        Utility function to wrap an input image with some number of border pixels.  By default, the
        number of border pixels is 7, but this function works as long as it's less than the size of
        the input image itself.  This function is used for periodic interpolation by the
        getShear() and other methods, but eventually if we make a 2d LookupTable-type class, this
        should become a method of that class.
        """
        # We should throw an exception if the image is smaller than 'border', since at this point
        # this process doesn't make sense.
        if im.bounds.xmax - im.bounds.xmin < border:
            raise RuntimeError("Periodic wrapping does not work with images this small!")
        expanded_bounds = im.bounds.withBorder(border)
        # Make new image with those bounds.
        im_new = galsim.ImageD(expanded_bounds)
        # Make the central subarray equal to what we want.
        im_new[im.bounds] = galsim.Image(im)
        # Set the empty bits around the center properly.  There are four strips around the edge, and
        # 4 corner squares that need to be filled in.  Surely there must be a smarter python-y way
        # of doing this, but I'm not clever enough to figure it out.  This is basically the grossest
        # code I've ever written, but it works properly.  Anyone who wants is welcome to fix it.
        #
        # Mike suggested a way to optimize it slightly, if we find that speed is an issue later on:
        # We can make just 4 copies, corresponding to
        # * Strip along left side.
        # * Upper left and strip along top can be done together.
        # * Lower left and strip along bottom can be done together.
        # * Upper right, strip along right, and lower right can be done together.
        # The code will also be a bit neater this way.
        #
        ## Strip along left-hand side
        b1 = border-1
        im_new[galsim.BoundsI(expanded_bounds.xmin, im.bounds.xmin-1,
                              im.bounds.ymin, im.bounds.ymax)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmax-b1,im.bounds.xmax,
                                                             im.bounds.ymin, im.bounds.ymax)])
        ## Strip along right-hand side
        im_new[galsim.BoundsI(im.bounds.xmax+1, expanded_bounds.xmax,
                              im.bounds.ymin, im.bounds.ymax)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmin, im.bounds.xmin+b1,
                                                             im.bounds.ymin, im.bounds.ymax)])
        ## Strip along the bottom
        im_new[galsim.BoundsI(im.bounds.xmin, im.bounds.xmax,
                              expanded_bounds.ymin, im.bounds.ymin-1)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmin, im.bounds.xmax,
                                                             im.bounds.ymax-b1, im.bounds.ymax)])
        ## Strip along the top
        im_new[galsim.BoundsI(im.bounds.xmin, im.bounds.xmax,
                              im.bounds.ymax+1, expanded_bounds.ymax)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmin, im.bounds.xmax,
                                                             im.bounds.ymin, im.bounds.ymin+b1)])
        ## Lower-left corner
        im_new[galsim.BoundsI(expanded_bounds.xmin, im.bounds.xmin-1,
                              expanded_bounds.ymin, im.bounds.ymin-1)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmax-b1, im.bounds.xmax,
                                                             im.bounds.ymax-b1, im.bounds.ymax)])
        ## Upper-right corner
        im_new[galsim.BoundsI(im.bounds.xmax+1, expanded_bounds.xmax,
                              im.bounds.ymax+1, expanded_bounds.ymax)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmin, im.bounds.xmin+b1,
                                                             im.bounds.ymin, im.bounds.ymin+b1)])
        ## Upper-left corner
        im_new[galsim.BoundsI(expanded_bounds.xmin, im.bounds.xmin-1,
                              im.bounds.ymax+1, expanded_bounds.ymax)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmax-b1, im.bounds.xmax,
                                                             im.bounds.ymin, im.bounds.ymin+b1)])
        ## Lower-right corner
        im_new[galsim.BoundsI(im.bounds.xmax+1, expanded_bounds.xmax,
                              expanded_bounds.ymin, im.bounds.ymin-1)] = \
                              galsim.Image(im[galsim.BoundsI(im.bounds.xmin, im.bounds.xmin+b1,
                                                             im.bounds.ymax-b1, im.bounds.ymax)])
        return im_new

    def getShear(self, pos, units=galsim.arcsec, reduced=True, periodic=False, interpolant=None):
        """
        This function can interpolate between grid positions to find the shear values for a given
        list of input positions (or just a single position).  Before calling this function, you must
        call buildGrid() first to define the grid of shears and convergences on which to
        interpolate.  The docstring for buildGrid() provides some guidance on appropriate grid
        configurations to use when building a grid that is to be later interpolated to random
        positions.

        By default, this method returns the reduced shear, which is defined in terms of shear and
        convergence as reduced shear `g=gamma/(1-kappa)`; the `reduced` keyword can be set to False
        in order to return the non-reduced shear.

        Note that the interpolation (carried out using the interpolant that was specified when
        building the gridded shears, if none is specified here) modifies the effective shear power
        spectrum and correlation function somewhat, though the effects can be limited by careful
        choice of grid parameters (see buildGrid() docstring for details).  Assuming those
        guidelines are followed, then the shear correlation function modifications due to use of the
        quintic, Lanczos-3, and Lanczos-5 interpolants are below 5% on all scales from the grid
        spacing to the total grid extent, typically below 2%.  The linear, cubic, and nearest
        interpolants perform significantly more poorly, with modifications of the correlation
        functions that can reach tens of percent on the scales where the recommended interpolants
        perform well.  Thus, the default interpolant is Lanczos-5, and users should think carefully
        about the acceptability of significant modification of the shear correlation function before
        changing to use linear, cubic, or nearest.

        Users who wish to ensure that the shear power spectrum is preserved post-interpolation
        should consider using the `periodic` interpolation option, which assumes the shear field is
        periodic (i.e., the sky is tiled with many copies of the given shear field).  Those who care
        about the correlation function should not use this option, and for this reason it's not the
        default.

        Some examples of how to use getShear():

        1. Get the shear for a particular point:

                >>> g1, g2 = my_ps.getShear(pos = galsim.PositionD(12, 412))

           This time the returned values are just floats and correspond to the shear for the
           provided position.

        2. You can also provide a position as a tuple to save the explicit PositionD construction:

                >>> g1, g2 = my_ps.getShear(pos = (12, 412))

        3. Get the shears for a bunch of points at once:

                >>> xlist = [ 141, 313,  12, 241, 342 ]
                >>> ylist = [  75, 199, 306, 225, 489 ]
                >>> poslist = [ galsim.PositionD(xlist[i],ylist[i]) for i in range(len(xlist)) ]
                >>> g1, g2 = my_ps.getShear( poslist )
                >>> g1, g2 = my_ps.getShear( (xlist, ylist) )

           Both calls do the same thing.  The returned g1, g2 this time are lists of g1, g2 values.
           The lists are the same length as the number of input positions.

        @param pos          Position(s) of the source(s), assumed to be post-lensing!
                            Valid ways to input this:
                                - Single PositionD (or PositionI) instance
                                - tuple of floats: (x,y)
                                - list of PositionD (or PositionI) instances
                                - tuple of lists: ( xlist, ylist )
                                - NumPy array of PositionD (or PositionI) instances
                                - tuple of NumPy arrays: ( xarray, yarray )
                                - Multidimensional NumPy array, as long as array[0] contains
                                  x-positions and array[1] contains y-positions
        @param units        The angular units used for the positions.  [default: arcsec]
        @param reduced      Whether returned shear(s) should be reduced shears. [default: True]
        @param periodic     Whether the interpolation should treat the positions as being defined
                            with respect to a periodic grid, which will wrap them around if they
                            are outside the bounds of the original grid on which shears were
                            defined.  If not, then shears are set to zero for positions outside the
                            original grid. [default: False]
        @param interpolant  Interpolant that will be used for interpolating the gridded shears.
                            By default, the one that was specified when building the grid was used.
                            Specifying an interpolant here does not change the one that is stored
                            as part of this PowerSpectrum instance. [default: None]

        @returns the shear as a tuple, (g1,g2)

        If the input `pos` is given a single position, (g1,g2) are the two shear components.
        If the input `pos` is given a list of positions, they are each a python list of values.
        If the input `pos` is given a NumPy array of positions, they are NumPy arrays.
        """

        if not hasattr(self, 'im_g1'):
            raise RuntimeError("PowerSpectrum.buildGrid must be called before getShear")

        # Convert to numpy arrays for internal usage:
        pos_x, pos_y = galsim.utilities._convertPositions(pos, units, 'getShear')

        # Set the interpolant:
        if interpolant is not None:
            xinterp = galsim.utilities.convert_interpolant(interpolant)
        else:
            xinterp = galsim.utilities.convert_interpolant(self.interpolant)
        kinterp = galsim.Quintic()

        if reduced:
            # get reduced shear (just discard magnification)
            g1_r, g2_r, _ = galsim.lensing_ps.theoryToObserved(self.im_g1.array, self.im_g2.array,
                                                               self.im_kappa.array)
            g1_r = galsim.ImageD(g1_r)
            g2_r = galsim.ImageD(g2_r)
            # Make an SBInterpolatedImage, which will do the heavy lifting for the interpolation.
            # However, if we are doing wrapped interpolation then we will want to manually stick the
            # wrapped grid bits around the edges, because otherwise the interpolant will treat
            # everything off the edges as zero.
            if periodic:
                # Make an expanded image.  We expand by 7 (default) to be safe, though most
                # interpolants don't need that much.  Note that we do NOT overwrite the stored data
                # in the PowerSpectrum instance with anything that is done here, so what's being
                # done here must be redone in subsequent calls to getShear with periodic
                # interpolation.
                g1_r_new = self._wrap_image(g1_r)
                g2_r_new = self._wrap_image(g2_r)

                # Then make the SBInterpolated image.
                sbii_g1 = galsim._galsim.SBInterpolatedImage(
                    g1_r_new.image, xInterp=xinterp, kInterp=kinterp)
                sbii_g2 = galsim._galsim.SBInterpolatedImage(
                    g2_r_new.image, xInterp=xinterp, kInterp=kinterp)
            else:
                sbii_g1 = galsim._galsim.SBInterpolatedImage(
                    g1_r.image, xInterp=xinterp, kInterp=kinterp)
                sbii_g2 = galsim._galsim.SBInterpolatedImage(
                    g2_r.image, xInterp=xinterp, kInterp=kinterp)
        else:
            if periodic:
                # Need to expand array here, as well.
                g1_r_new = self._wrap_image(self.im_g1)
                g2_r_new = self._wrap_image(self.im_g2)
                sbii_g1 = galsim._galsim.SBInterpolatedImage(
                    g1_r_new.image, xInterp=xinterp, kInterp=kinterp)
                sbii_g2 = galsim._galsim.SBInterpolatedImage(
                    g2_r_new.image, xInterp=xinterp, kInterp=kinterp)
            else:
                sbii_g1 = galsim._galsim.SBInterpolatedImage(self.im_g1.image, xInterp=xinterp,
                                                             kInterp=kinterp)
                sbii_g2 = galsim._galsim.SBInterpolatedImage(self.im_g2.image, xInterp=xinterp,
                                                             kInterp=kinterp)

        # Calculate some numbers that are useful to calculate before the loop over positions, but
        # only if we are doing a periodic treatment of the box.
        if periodic:
            dx = self.bounds.xmax-self.bounds.xmin
            dy = self.bounds.ymax-self.bounds.ymin

        # interpolate if necessary
        g1,g2 = [], []
        for iter_pos in [ galsim.PositionD(pos_x[i],pos_y[i]) for i in range(len(pos_x)) ]:
            # Check that the position is in the bounds of the interpolated image
            if not self.bounds.includes(iter_pos):
                if not periodic:
                    # We're not treating this as a periodic box, so issue a warning and set the
                    # shear to zero for positions that are outside the original grid.
                    import warnings
                    warnings.warn(
                        "Warning: position (%f,%f) not within the bounds "%(iter_pos.x,iter_pos.y) +
                        "of the gridded shear values: " + str(self.bounds) +
                        ".  Returning a shear of (0,0) for this point.")
                    g1.append(0.)
                    g2.append(0.)
                else:
                    # Treat this as a periodic box.
                    wrap_pos = galsim.PositionD(
                        (iter_pos.x-self.bounds.xmin) % dx + self.bounds.xmin,
                        (iter_pos.y-self.bounds.ymin) % dy + self.bounds.ymin
                        )
                    g1.append(sbii_g1.xValue((wrap_pos-self.center)/self.grid_spacing))
                    g2.append(sbii_g2.xValue((wrap_pos-self.center)/self.grid_spacing))
            else:
                g1.append(sbii_g1.xValue((iter_pos-self.center)/self.grid_spacing))
                g2.append(sbii_g2.xValue((iter_pos-self.center)/self.grid_spacing))

        if isinstance(pos, galsim.PositionD):
            return g1[0], g2[0]
        elif isinstance(pos[0], np.ndarray):
            return np.array(g1), np.array(g2)
        elif len(pos_x) == 1 and not isinstance(pos[0],list):
            return g1[0], g2[0]
        else:
            return g1, g2

    def getConvergence(self, pos, units=galsim.arcsec, periodic=False, interpolant=None):
        """
        This function can interpolate between grid positions to find the convergence values for a
        given list of input positions (or just a single position).  Before calling this function,
        you must call buildGrid() first to define the grid of convergences on which to interpolate.
        The docstring for buildGrid() provides some guidance on appropriate grid configurations to
        use when building a grid that is to be later interpolated to random positions.

        Note that the interpolation (carried out using the interpolant that was specified when
        building the gridded shears and convergence, if none is specified here) modifies the
        effective 2-point functions of these quantities.  See docstring for getShear() docstring for
        caveats about interpolation.  The user is advised to be very careful about deviating from
        the default Lanczos-5 interpolant.

        The usage of getConvergence() is the same as for getShear(), except that it returns only a
        single quantity (convergence value or array of convergence values) rather than two
        quantities.  See documentation for getShear() for some examples.

        @param pos          Position(s) of the source(s), assumed to be post-lensing!
                            Valid ways to input this:
                                - Single PositionD (or PositionI) instance
                                - tuple of floats: (x,y)
                                - list of PositionD (or PositionI) instances
                                - tuple of lists: ( xlist, ylist )
                                - NumPy array of PositionD (or PositionI) instances
                                - tuple of NumPy arrays: ( xarray, yarray )
                                - Multidimensional NumPy array, as long as array[0] contains
                                  x-positions and array[1] contains y-positions
        @param units        The angular units used for the positions.  [default: arcsec]
        @param periodic     Whether the interpolation should treat the positions as being defined
                            with respect to a periodic grid, which will wrap them around if they
                            are outside the bounds of the original grid on which shears and
                            convergences were defined.  If not, then convergences are set to zero
                            for positions outside the original grid.  [default: False]
        @param interpolant  Interpolant that will be used for interpolating the gridded shears.
                            By default, the one that was specified when building the grid was used.
                            Specifying an interpolant here does not change the one that is stored
                            as part of this PowerSpectrum instance. [default: None]

        @returns the convergence, kappa.

        If the input `pos` is given a single position, kappa is the convergence value.
        If the input `pos` is given a list of positions, kappa is a python list of values.
        If the input `pos` is given a NumPy array of positions, kappa is a NumPy array.
        """

        if not hasattr(self, 'im_kappa'):
            raise RuntimeError("PowerSpectrum.buildGrid must be called before getConvergence")

        # Convert to numpy arrays for internal usage:
        pos_x, pos_y = galsim.utilities._convertPositions(pos, units, 'getConvergence')

        # Set the interpolant:
        if interpolant is not None:
            xinterp = galsim.utilities.convert_interpolant(interpolant)
        else:
            xinterp = galsim.utilities.convert_interpolant(self.interpolant)
        kinterp = galsim.Quintic()

        # Make an SBInterpolatedImage, which will do the heavy lifting for the interpolation.
        # However, if we are doing wrapped interpolation then we will want to manually stick the
        # wrapped grid bits around the edges, because otherwise the interpolant will treat
        # everything off the edges as zero.
        if periodic:
            # Make an expanded bounds.  We expand by 7 (default) to be safe, though most
            # interpolants don't need that much.
            kappa_new = self._wrap_image(self.im_kappa)

            # Then make the SBInterpolated image.
            sbii_kappa = galsim._galsim.SBInterpolatedImage(
                kappa_new.image, xInterp=xinterp, kInterp=kinterp)
        else:
            sbii_kappa = galsim._galsim.SBInterpolatedImage(
                self.im_kappa.image, xInterp=xinterp, kInterp=kinterp)

        # Calculate some numbers that are useful to calculate before the loop over positions, but
        # only if we are doing a periodic treatment of the box.
        if periodic:
            dx = self.bounds.xmax-self.bounds.xmin
            dy = self.bounds.ymax-self.bounds.ymin

        # interpolate if necessary
        kappa = []
        for iter_pos in [ galsim.PositionD(pos_x[i],pos_y[i]) for i in range(len(pos_x)) ]:
            # Check that the position is in the bounds of the interpolated image
            if not self.bounds.includes(iter_pos):
                if not periodic:
                    import warnings
                    warnings.warn(
                        "Warning: position (%f,%f) not within the bounds "%(iter_pos.x,iter_pos.y) +
                        "of the gridded convergence values: " + str(self.bounds) +
                        ".  Returning a convergence of 0 for this point.")
                    kappa.append(0.)
                else:
                    # Treat this as a periodic box.
                    wrap_pos = galsim.PositionD(
                        (iter_pos.x-self.bounds.xmin) % dx + self.bounds.xmin,
                        (iter_pos.y-self.bounds.ymin) % dy + self.bounds.ymin
                        )
                    kappa.append(sbii_kappa.xValue((wrap_pos-self.center)/self.grid_spacing))
            else:
                kappa.append(sbii_kappa.xValue((iter_pos-self.center)/self.grid_spacing))

        if isinstance(pos, galsim.PositionD):
            return kappa[0]
        elif isinstance(pos[0], np.ndarray):
            return np.array(kappa)
        elif len(pos_x) == 1 and not isinstance(pos[0],list):
            return kappa[0]
        else:
            return kappa

    def getMagnification(self, pos, units=galsim.arcsec, periodic=False, interpolant=None):
        """
        This function can interpolate between grid positions to find the lensing magnification (mu)
        values for a given list of input positions (or just a single position).  Before calling this
        function, you must call buildGrid() first to define the grid of shears and convergences on
        which to interpolate.  The docstring for buildGrid() provides some guidance on appropriate
        grid configurations to use when building a grid that is to be later interpolated to random
        positions.

        Note that the interpolation (carried out using the interpolant that was specified when
        building the gridded shears and convergence, if none is specified here) modifies the
        effective 2-point functions of these quantities.  See docstring for getShear() docstring for
        caveats about interpolation.  The user is advised to be very careful about deviating from
        the default Lanczos-5 interpolant.

        The usage of getMagnification() is the same as for getShear(), except that it returns only a
        single quantity (a magnification value or array of magnification values) rather than a pair
        of quantities.  See documentation for getShear() for some examples.

        @param pos              Position(s) of the source(s), assumed to be post-lensing!
                                Valid ways to input this:
                                  - Single PositionD (or PositionI) instance
                                  - tuple of floats: (x,y)
                                  - list of PositionD (or PositionI) instances
                                  - tuple of lists: ( xlist, ylist )
                                  - NumPy array of PositionD (or PositionI) instances
                                  - tuple of NumPy arrays: ( xarray, yarray )
                                  - Multidimensional NumPy array, as long as array[0] contains
                                    x-positions and array[1] contains y-positions
        @param units            The angular units used for the positions.  [default: arcsec]
        @param periodic         Whether the interpolation should treat the positions as being
                                defined with respect to a periodic grid, which will wrap them around
                                if they are outside the bounds of the original grid on which shears
                                and convergences were defined.  If not, then magnification is set to
                                1 for positions outside the original grid.  [default: False]
        @param interpolant      Interpolant that will be used for interpolating the gridded shears.
                                By default, the one that was specified when building the grid was
                                used.  Specifying an interpolant here does not change the one that
                                is stored as part of this PowerSpectrum instance. [default: None]

        @returns the magnification, mu.

        If the input `pos` is given a single position, mu is the magnification value.
        If the input `pos` is given a list of positions, mu is a python list of values.
        If the input `pos` is given a NumPy array of positions, mu is a NumPy array.
        """

        if not hasattr(self, 'im_kappa'):
            raise RuntimeError("PowerSpectrum.buildGrid must be called before getMagnification")

        # Convert to numpy arrays for internal usage:
        pos_x, pos_y = galsim.utilities._convertPositions(pos, units, 'getMagnification')

        # Set the interpolant:
        if interpolant is not None:
            xinterp = galsim.utilities.convert_interpolant(interpolant)
        else:
            xinterp = galsim.utilities.convert_interpolant(self.interpolant)
        kinterp = galsim.Quintic()

        # Calculate the magnification based on the convergence and shear
        _, _, mu = galsim.lensing_ps.theoryToObserved(self.im_g1.array, self.im_g2.array,
                                                      self.im_kappa.array)
        # Interpolate mu-1, so the zero values off the edge are appropriate.
        im_mu = galsim.ImageD(mu-1)

        # Make an SBInterpolatedImage, which will do the heavy lifting for the interpolation.
        # However, if we are doing wrapped interpolation then we will want to manually stick the
        # wrapped grid bits around the edges, because otherwise the interpolant will treat
        # everything off the edges as zero.
        if periodic:
            # Make an expanded bounds.  We expand by 7 (default) to be safe, though most
            # interpolants don't need that much.
            im_mu_new = self._wrap_image(im_mu)

            # Then make the SBInterpolated image.
            sbii_mu = galsim._galsim.SBInterpolatedImage(im_mu_new.image, xInterp=xinterp,
                                                         kInterp=kinterp)
        else:
            sbii_mu = galsim._galsim.SBInterpolatedImage(im_mu.image, xInterp=xinterp,
                                                         kInterp=kinterp)

        # Calculate some numbers that are useful to calculate before the loop over positions, but
        # only if we are doing a periodic treatment of the box.
        if periodic:
            dx = self.bounds.xmax-self.bounds.xmin
            dy = self.bounds.ymax-self.bounds.ymin

        # interpolate if necessary
        mu = []
        for iter_pos in [ galsim.PositionD(pos_x[i],pos_y[i]) for i in range(len(pos_x)) ]:
            # Check that the position is in the bounds of the interpolated image
            if not self.bounds.includes(iter_pos):
                if not periodic:
                    import warnings
                    warnings.warn(
                        "Warning: position (%f,%f) not within the bounds "%(iter_pos.x,iter_pos.y) +
                        "of the gridded convergence values: " + str(self.bounds) +
                        ".  Returning a magnification of 1 for this point.")
                    mu.append(1.)
                else:
                    # Treat this as a periodic box.
                    wrap_pos = galsim.PositionD(
                        (iter_pos.x-self.bounds.xmin) % dx + self.bounds.xmin,
                        (iter_pos.y-self.bounds.ymin) % dy + self.bounds.ymin
                        )
                    mu.append(sbii_mu.xValue((wrap_pos-self.center)/self.grid_spacing)+1.)

            else:
                mu.append(sbii_mu.xValue((iter_pos-self.center)/self.grid_spacing)+1.)

        if isinstance(pos, galsim.PositionD):
            return mu[0]
        elif isinstance(pos[0], np.ndarray):
            return np.array(mu)
        elif len(pos_x) == 1 and not isinstance(pos[0],list):
            return mu[0]
        else:
            return mu

    def getLensing(self, pos, units=galsim.arcsec, periodic=False, interpolant=None):
        """
        This function can interpolate between grid positions to find the lensing observable
        quantities (reduced shears g1 and g2, and magnification mu) for a given list of input
        positions (or just a single position).  Before calling this function, you must call
        buildGrid() first to define the grid of shears and convergences on which to interpolate. The
        docstring for buildGrid() provides some guidance on appropriate grid configurations to use
        when building a grid that is to be later interpolated to random positions.

        Note that the interpolation (carried out using the interpolant that was specified when
        building the gridded shears and convergence, if none is specified here) modifies the
        effective 2-point functions of these quantities.  See docstring for getShear() docstring for
        caveats about interpolation.  The user is advised to be very careful about deviating from
        the default Lanczos-5 interpolant.

        The usage of getLensing() is the same as for getShear(), except that it returns three
        quantities (two reduced shear components and magnification) rather than two.  See
        documentation for getShear() for some examples.

        @param pos              Position(s) of the source(s), assumed to be post-lensing!
                                Valid ways to input this:
                                  - Single PositionD (or PositionI) instance
                                  - tuple of floats: (x,y)
                                  - list of PositionD (or PositionI) instances
                                  - tuple of lists: ( xlist, ylist )
                                  - NumPy array of PositionD (or PositionI) instances
                                  - tuple of NumPy arrays: ( xarray, yarray )
                                  - Multidimensional NumPy array, as long as array[0] contains
                                    x-positions and array[1] contains y-positions
        @param units            The angular units used for the positions.  [default: arcsec]
        @param periodic         Whether the interpolation should treat the positions as being
                                defined with respect to a periodic grid, which will wrap them around
                                if they are outside the bounds of the original grid on which shears
                                and convergences were defined.  If not, then shear is set to zero
                                and magnification is set to 1 for positions outside the original
                                grid.  [default: False]
        @param interpolant      Interpolant that will be used for interpolating the gridded shears.
                                By default, the one that was specified when building the grid was
                                used.  Specifying an interpolant here does not change the one that
                                is stored as part of this PowerSpectrum instance. [default: None]

        @returns shear and magnification as a tuple (g1,g2,mu).

        If the input `pos` is given a single position, the return values are the shear and
        magnification values at that position.
        If the input `pos` is given a list of positions, they are python lists of values.
        If the input `pos` is given a NumPy array of positions, they are NumPy arrays.
        """

        if not hasattr(self, 'im_kappa'):
            raise RuntimeError("PowerSpectrum.buildGrid must be called before getLensing")

        # Convert to numpy arrays for internal usage:
        pos_x, pos_y = galsim.utilities._convertPositions(pos, units, 'getLensing')

        # Set the interpolant:
        if interpolant is not None:
            xinterp = galsim.utilities.convert_interpolant(interpolant)
        else:
            xinterp = galsim.utilities.convert_interpolant(self.interpolant)
        kinterp = galsim.Quintic()

        # Calculate the magnification based on the convergence and shear
        g1_r, g2_r, mu = galsim.lensing_ps.theoryToObserved(self.im_g1.array, self.im_g2.array,
                                                            self.im_kappa.array)
        im_g1_r = galsim.ImageD(g1_r)
        im_g2_r = galsim.ImageD(g2_r)
        im_mu = galsim.ImageD(mu-1)

        # Make an SBInterpolatedImage, which will do the heavy lifting for the interpolation.
        # However, if we are doing wrapped interpolation then we will want to manually stick the
        # wrapped grid bits around the edges, because otherwise the interpolant will treat
        # everything off the edges as zero.
        if periodic:
            # Make an expanded bounds.  We expand by 7 (default) to be safe, though most
            # interpolants don't need that much.
            im_mu_new = self._wrap_image(im_mu)
            im_g1_new = self._wrap_image(im_g1_r)
            im_g2_new = self._wrap_image(im_g2_r)

            # Then make the SBInterpolated image.
            sbii_g1 = galsim._galsim.SBInterpolatedImage(im_g1_new.image, xInterp=xinterp,
                                                         kInterp=kinterp)
            sbii_g2 = galsim._galsim.SBInterpolatedImage(im_g2_new.image, xInterp=xinterp,
                                                         kInterp=kinterp)
            sbii_mu = galsim._galsim.SBInterpolatedImage(im_mu_new.image, xInterp=xinterp,
                                                         kInterp=kinterp)
        else:
            sbii_g1 = galsim._galsim.SBInterpolatedImage(im_g1_r.image, xInterp=xinterp,
                                                         kInterp=kinterp)
            sbii_g2 = galsim._galsim.SBInterpolatedImage(im_g2_r.image, xInterp=xinterp,
                                                         kInterp=kinterp)
            sbii_mu = galsim._galsim.SBInterpolatedImage(im_mu.image, xInterp=xinterp,
                                                         kInterp=kinterp)

        # Calculate some numbers that are useful to calculate before the loop over positions, but
        # only if we are doing a periodic treatment of the box.
        if periodic:
            dx = self.bounds.xmax-self.bounds.xmin
            dy = self.bounds.ymax-self.bounds.ymin

        # interpolate if necessary
        g1, g2, mu = [], [], []
        for iter_pos in [ galsim.PositionD(pos_x[i],pos_y[i]) for i in range(len(pos_x)) ]:
            # Check that the position is in the bounds of the interpolated image
            if not self.bounds.includes(iter_pos):
                if not periodic:
                    import warnings
                    warnings.warn(
                        "Warning: position (%f,%f) not within the bounds "%(iter_pos.x,iter_pos.y) +
                        "of the gridded values: " + str(self.bounds) +
                        ".  Returning 0 for lensing observables at this point.")
                    g1.append(0.)
                    g2.append(0.)
                    mu.append(1.)
                else:
                    # Treat this as a periodic box.
                    wrap_pos = galsim.PositionD(
                        (iter_pos.x-self.bounds.xmin) % dx + self.bounds.xmin,
                        (iter_pos.y-self.bounds.ymin) % dy + self.bounds.ymin
                        )
                    g1.append(sbii_g1.xValue((wrap_pos-self.center)/self.grid_spacing))
                    g2.append(sbii_g2.xValue((wrap_pos-self.center)/self.grid_spacing))
                    mu.append(sbii_mu.xValue((wrap_pos-self.center)/self.grid_spacing)+1.)

            else:
                g1.append(sbii_g1.xValue((iter_pos-self.center)/self.grid_spacing))
                g2.append(sbii_g2.xValue((iter_pos-self.center)/self.grid_spacing))
                mu.append(sbii_mu.xValue((iter_pos-self.center)/self.grid_spacing)+1.)

        if isinstance(pos, galsim.PositionD):
            return g1[0], g2[0], mu[0]
        elif isinstance(pos[0], np.ndarray):
            return np.array(g1), np.array(g2), np.array(mu)
        elif len(pos_x) == 1 and not isinstance(pos[0],list):
            return g1[0], g2[0], mu[0]
        else:
            return g1, g2, mu

class PowerSpectrumRealizer(object):
    """Class for generating realizations of power spectra with any area and pixel size.

    This class is not one that end-users should expect to interact with.  It is designed to quickly
    generate many realizations of the same shear power spectra on a square grid.  The initializer
    sets up the grids in k-space and computes the power on them.  It also computes spin weighting
    terms.  You can alter any of the setup properties later.  It currently only works for square
    grids (at least, much of the internals would be incorrect for non-square grids), so while it
    nominally contains arrays that could be allowed to be non-square, the constructor itself
    enforces squareness.

    @param ngrid            The size of the grid in one dimension.
    @param pixel_size       The size of the pixel sides, in units consistent with the units expected
                            by the power spectrum functions.
    @param p_E              Equivalent to e_power_function in the documentation for the
                            PowerSpectrum class.
    @param p_B              Equivalent to b_power_function in the documentation for the
                            PowerSpectrum class.
    """
    def __init__(self, ngrid, pixel_size, p_E, p_B):
        # Set up the k grids in x and y, and the instance variables
        self.set_size(ngrid, pixel_size)
        self.set_power(p_E, p_B)

    def __repr__(self):
        return "galsim.lensing_ps.PowerSpectrumRealizer(ngrid=%r, pixel_size=%r, p_E=%r, p_B=%r)"%(
                self.nx, self.pixel_size, self.p_E, self.p_B)
    def __str__(self):
        return "galsim.lensing_ps.PowerSpectrumRealizer(ngrid=%r, pixel_size=%r, p_E=%s, p_B=%s)"%(
                self.nx, self.pixel_size, self.p_E, self.p_B)
    def __eq__(self, other): return repr(self) == repr(other)
    def __ne__(self, other): return not self.__eq__(other)
    def __hash__(self): return hash(repr(self))

    def set_size(self, ngrid, pixel_size):
        self.nx = ngrid
        self.ny = ngrid
        self.pixel_size = float(pixel_size)

        # Setup some handy slices for indexing different parts of k space
        self.ikx = slice(0,self.nx//2+1)       # positive kx values, including 0, nx/2
        self.ikxp = slice(1,(self.nx+1)//2)    # limit to only values with a negative value
        self.ikxn = slice(-1,self.nx//2,-1)    # negative kx values

        # We always call this with nx=ny, so behavior with nx != ny is not tested.
        # However, we make a basic attempt to enable such behavior in the future if needed.
        self.iky = slice(0,self.ny//2+1)
        self.ikyp = slice(1,(self.ny+1)//2)
        self.ikyn = slice(-1,self.ny//2,-1)

        # Set up the scalar k grid. Generally, for a box size of L (in one dimension), the grid
        # spacing in k_x or k_y is Delta k=2pi/L
        self.kx, self.ky = galsim.utilities.kxky((self.ny,self.nx))
        self.kx /= self.pixel_size
        self.ky /= self.pixel_size

        # Compute the spin weightings
        self._generate_exp2ipsi()

    def set_power(self, p_E, p_B):
        self.p_E = p_E
        self.p_B = p_B
        if p_E is None:  self.amplitude_E = None
        else:            self.amplitude_E = np.sqrt(self._generate_power_array(p_E))/self.pixel_size
        if p_B is None:  self.amplitude_B = None
        else:            self.amplitude_B = np.sqrt(self._generate_power_array(p_B))/self.pixel_size

    def recompute_power(self):
        self.set_power(self.p_E, self.p_B)

    def __call__(self, gd):
        """Generate a realization of the current power spectrum.

        @param gd               A Gaussian deviate to use when generating the shear fields.

        @return a tuple of NumPy arrays (g1,g2,kappa) for the shear and convergence.
        """
        ISQRT2 = np.sqrt(1.0/2.0)

        if not isinstance(gd, galsim.GaussianDeviate):
            raise TypeError(
                "The gd provided to the PowerSpectrumRealizer is not a GaussianDeviate!")

        # Generate a random complex realization for the E-mode, if there is one
        if self.amplitude_E is not None:
            r1 = galsim.utilities.rand_arr(self.amplitude_E.shape, gd)
            r2 = galsim.utilities.rand_arr(self.amplitude_E.shape, gd)
            E_k = np.empty((self.ny,self.nx), dtype=complex)
            E_k[:,self.ikx] = self.amplitude_E * (r1 + 1j*r2) * ISQRT2
            # E_k corresponds to real kappa, so E_k[-k] = conj(E_k[k])
            self._make_hermitian(E_k)
        else: E_k = 0

        # Generate a random complex realization for the B-mode, if there is one
        if self.amplitude_B is not None:
            r1 = galsim.utilities.rand_arr(self.amplitude_B.shape, gd)
            r2 = galsim.utilities.rand_arr(self.amplitude_B.shape, gd)
            B_k = np.empty((self.ny,self.nx), dtype=complex)
            B_k[:,self.ikx] = self.amplitude_B * (r1 + 1j*r2) * ISQRT2
            # B_k corresponds to imag kappa, so B_k[-k] = -conj(B_k[k])
            # However, we later multiply this by i, so that means here B_k[-k] = conj(B_k[k])
            self._make_hermitian(B_k)
        else:
            B_k = 0

        # In terms of kappa, the E mode is the real kappa, and the B mode is imaginary kappa:
        # In fourier space, both E_k and B_k are complex, but the same E + i B relation holds.
        kappa_k = E_k + 1j * B_k

        # Compute gamma_k as exp(2i psi) kappa_k
        # Equation 2.1.12 of Kaiser & Squires (1993, ApJ, 404, 441) is equivalent to:
        #   gamma_k = -self.exp2ipsi * kappa_k
        # But of course, they only considered real (E-mode) kappa.
        # However, this equation has a sign error.  There should not be a minus in front.
        # If you follow their subsequent deviation, you will see that they drop the minus sign
        # when they get to 2.1.15 (another - appears from the derivative).  2.1.15 is correct.
        # e.g. it correctly produces a positive point mass for tangential shear ~ 1/r^2.
        # So this implies that the minus sign in 2.1.12 should not be there.
        gamma_k = self.exp2ipsi * kappa_k

        # And go to real space to get the real-space shear and convergence fields.
        # Note the multiplication by N is needed because the np.fft.ifft2 implicitly includes a
        # 1/N^2, and for proper normalization we need a factor of 1/N.
        gamma = self.nx * np.fft.ifft2(gamma_k)
        # Make them contiguous, since we need to use them in an Image, which requires it.
        g1 = np.ascontiguousarray(np.real(gamma))
        g2 = np.ascontiguousarray(np.imag(gamma))

        # Could do the same thing with kappa..
        #kappa = self.nx * np.fft.ifft2(kappa_k)
        #k = np.ascontiguousarray(np.real(kappa))

        # But, since we don't care about imag(kappa), this is a bit faster:
        if E_k is 0:
            k = np.zeros((self.ny,self.nx))
        else:
            k = self.nx * np.fft.irfft2(E_k[:,self.ikx], s=(self.ny,self.nx))

        return g1, g2, k

    def _make_hermitian(self, P_k):
        # Make P_k[-k] = conj(P_k[k])
        # First update the kx=0 values to be consistent with this.
        P_k[self.ikyn,0] = np.conj(P_k[self.ikyp,0])
        P_k[0,0] = np.real(P_k[0,0])  # Not reall necessary, since P_k[0,0] = 0, but
                                      # I do it anyway for the sake of pedantry...
        # Then fill the kx<0 values appropriately
        P_k[self.ikyp,self.ikxn] = np.conj(P_k[self.ikyn,self.ikxp])
        P_k[self.ikyn,self.ikxn] = np.conj(P_k[self.ikyp,self.ikxp])
        P_k[0,self.ikxn] = np.conj(P_k[0,self.ikxp])
        # For even nx,ny, there are a few more changes needed.
        if self.ny % 2 == 0:
            # Note: this is a bit more complicated if you have to separately check whether
            # nx and/or ny are even.  I ignore this subtlety until we decide it is needed.
            P_k[self.ikyn,self.nx//2] = np.conj(P_k[self.ikyp,self.nx//2])
            P_k[self.ny//2,self.ikxn] = np.conj(P_k[self.ny//2,self.ikxp])
            P_k[self.ny//2,0] = np.real(P_k[self.ny//2,0])
            P_k[0,self.nx//2] = np.real(P_k[0,self.nx//2])
            P_k[self.ny//2,self.nx//2] = np.real(P_k[self.ny//2,self.nx//2])

    def _generate_power_array(self, power_function):
        # Internal function to generate the result of a power function evaluated on a grid,
        # taking into account the symmetries.
        power_array = np.empty((self.ny, self.nx//2+1))

        # Set up the scalar |k| grid using just the positive kx,ky
        k = np.sqrt(self.kx[self.iky,self.ikx]**2 + self.ky[self.iky,self.ikx]**2)

        # Fudge the value at k=0, so we don't have to evaluate power there
        k[0,0] = k[1,0]
        # Raise a clear exception for LookupTable that are not defined on the full k range!
        if isinstance(power_function, galsim.LookupTable):
            mink = np.min(k)
            maxk = np.max(k)
            if mink < power_function.x_min or maxk > power_function.x_max:
                raise ValueError(
                    "LookupTable P(k) is not defined for full k range on grid, %f<k<%f"%(mink,maxk))
        P_k = power_function(k)

        # Now fix the k=0 value of power to zero
        assert type(P_k) is np.ndarray
        P_k[0,0] = type(P_k[0,1])(0.)
        if np.any(P_k < 0):
            raise ValueError("Negative power found for some values of k!")

        power_array[self.iky, self.ikx] = P_k
        power_array[self.ikyn, self.ikx] = P_k[self.ikyp, self.ikx]
        return power_array

    def _generate_exp2ipsi(self):
        # exp2ipsi = (kx + iky)^2 / |kx + iky|^2 is the phase of the k vector.
        kz = self.kx + self.ky*1j
        # exp(2i psi) = kz^2 / |kz|^2
        ksq = kz*np.conj(kz)
        # Need to adjust denominator for kz=0 to avoid division by 0.
        ksq[0,0] = 1.
        self.exp2ipsi = kz*kz/ksq
        # Note: this leaves exp2ipsi[0,0] = 0, but it turns out that's ok, since we only
        # ever multiply it by something that is 0 anyway (amplitude[0,0] = 0).

def kappaKaiserSquires(g1, g2):
    """Perform a Kaiser & Squires (1993) inversion to get a convergence map from gridded shears.

    This function takes gridded shears and constructs a convergence map from them.  While this is
    complicated in reality by the non-gridded galaxy positions, it is a straightforward
    implementation using Fourier transforms for the case of gridded galaxy positions.  Note that
    there are additional complications when dealing with real observational issues like shape noise
    that are not handled by this function, and likewise there are known edge effects.

    Note that, like any process that attempts to recover information from discretely sampled data,
    the `kappa_E` and `kappa_B` maps returned by this function are subject to aliasing.  There will
    be distortions if there are non-zero frequency modes in the lensing field represented by `g1`
    and `g2` at more than half the frequency represented by the `g1`, `g2` grid spacing.  To avoid
    this issue in practice you can smooth the input `g1`, `g2` to effectively bandlimit them (the
    same smoothing kernel will be present in the output `kappa_E`, `kappa_B`).  If applying this
    function to shears drawn randomly according to some power spectrum, the power spectrum that is
    used should be modified to go to zero above the relevant maximum k value for the grid being
    used.

    @param g1  Square Image or NumPy array containing the first component of shear.
    @param g2  Square Image or NumPy array containing the second component of shear.

    @returns the tuple (kappa_E, kappa_B), as NumPy arrays.

    The returned kappa_E represents the convergence field underlying the input shears.
    The returned kappa_B is the convergence field generated were all shears rotated by 45 degrees
    prior to input.
    """
    # Checks on inputs
    if isinstance(g1, galsim.Image) and isinstance(g2, galsim.Image):
        g1 = g1.array
        g2 = g2.array
    elif isinstance(g1, np.ndarray) and isinstance(g2, np.ndarray):
        pass
    else:
        raise TypeError("Input g1 and g2 must be galsim Image or NumPy arrays.")
    if g1.shape != g2.shape:
        raise ValueError("Input g1 and g2 must be the same shape.")
    if g1.shape[0] != g1.shape[1]:
        raise NotImplementedError("Non-square input shear grids not supported.")

    # Then setup the kx, ky grids
    kx, ky = galsim.utilities.kxky(g1.shape)
    kz = kx + ky*1j

    # exp(2i psi) = kz^2 / |kz|^2
    ksq = kz*np.conj(kz)
    # Need to adjust denominator for kz=0 to avoid division by 0.
    ksq[0,0] = 1.
    exp2ipsi = kz*kz/ksq

    # Build complex g = g1 + i g2
    gz = g1 + g2*1j

    # Go to fourier space
    gz_k = np.fft.fft2(gz)

    # Equation 2.1.12 of Kaiser & Squires (1993) is equivalent to:
    #   kz_k = -np.conj(exp2ipsi)*gz_k
    # However, this equation has a sign error.  There should not be a minus in front.
    # If you follow their subsequent deviation, you will see that they drop the minus sign
    # when they get to 2.1.15 (another - appears from the derivative).  2.1.15 is correct.
    # e.g. it correctly produces a positive point mass for tangential shear ~ 1/r^2.
    # So this implies that the minus sign in 2.1.12 should not be there.
    kz_k = np.conj(exp2ipsi)*gz_k

    # Come back to real space
    kz = np.fft.ifft2(kz_k)

    # kz = kappa_E + i kappa_B
    kappaE = np.real(kz)
    kappaB = np.imag(kz)
    return kappaE, kappaB

class xip_integrand:
    """Utility class to assist in calculating the xi_+ shear correlation function from power
    spectra."""
    def __init__(self, pk, r):
        self.pk = pk
        self.r = r
    def __call__(self, k):
        return k * self.pk(k) * galsim.bessel.j0(self.r*k)

class xim_integrand:
    """Utility class to assist in calculating the xi_- shear correlation function from power
    spectra."""
    def __init__(self, pk, r):
        self.pk = pk
        self.r = r
    def __call__(self, k):
        return k * self.pk(k) * galsim.bessel.jn(4,self.r*k)
