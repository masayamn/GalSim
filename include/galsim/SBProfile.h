// -*- c++ -*-
#ifndef SBPROFILE_H
#define SBPROFILE_H

/** 
 * @file SBProfile.h @brief Contains a class definition for two-dimensional Surface Brightness 
 * Profiles.
 *
 * The SBProfiles include common star, galaxy, and PSF shapes.
 * If you have not defined USE_LAGUERRE, the SBLaguerre class will be skipped.
 * If you have not defined USE_IMAGES, all of the drawing routines are disabled but you will no 
 * longer be dependent on the Image and FITS classes.
 */

#include <cmath>
#include <list>
#include <map>
#include <vector>
#include <algorithm>

/**
 * Remove this to disable the drawing routines. Also removes dependencies on Image and FITS classes.
 */
#define USE_IMAGES 

#define USE_LAGUERRE ///< Remove this to skip the SBLaguerre classes.

#include "Std.h"
#include "Shear.h"
#include "FFT.h"
#include "Table.h"
#include "Random.h"

#ifdef USE_IMAGES
#include "Image.h"
#endif

#ifdef USE_LAGUERRE
#include "Laguerre.h"
#endif

// ??? could += for SBAdd, or *= to SBConvolve
// ??? Ask for super-Nyquist sampling factor in draw??
namespace galsim {

    /// @brief Exception class thrown by SBProfiles.
    class SBError : public std::runtime_error 
    {
    public:
        SBError(const std::string& m="") : std::runtime_error("SB Error: " + m) {}
    };

    /** @brief Class to hold a list of "photon" arrival positions
     * 
     * Class holds a vector of information about photon arrivals: x and y positions, and a flux
     * carried by each photon.  It is the intention that fluxes of photons be nearly equal in absolute 
     * value so that noise statistics can be estimated by counting number of positive and negative photons.
     * This class holds the code that allows its flux to be added to a surface-brightness Image.
     */
    class PhotonArray 
    {
    public:
        /** 
         * @brief Construct an array of given size with zero-flux photons
         *
         * @param[in] N Size of desired array.
         */
        explicit PhotonArray(int N): _x(N,0.), _y(N,0.), _flux(N,0.) {}

        /** 
         * @brief Construct from three vectors.  Exception if vector sizes do not match.
         *
         * @param[in] vx vector of photon x coordinates
         * @param[in] vy vector of photon y coordinates
         * @param[in] vflux vector of photon fluxes
         */
        PhotonArray(std::vector<double>& vx, std::vector<double>& vy, std::vector<double>& vflux);

        /**
         * @brief Accessor for array size
         *
         * @returns Array size
         */
        int size() const {return _x.size();}

        /** @brief reserve space in arrays for future elements
         *
         * @param[in] N number of elements to reserve space for.
         */
        void reserve(int N) {
            _x.reserve(N);
            _y.reserve(N);
            _flux.reserve(N);
        }

        /**
         * @brief Set characteristics of a photon
         *
         * @param[in] i Index of desired photon (no bounds checking)
         * @param[in] x x coordinate of photon
         * @param[in] y y coordinate of photon
         * @param[in] flux flux of photon
         */
        void setPhoton(int i, double x, double y, double flux) {
            _x[i]=x; 
            _y[i]=y;
            _flux[i]=flux;
        }
        /**
         * @brief Access x coordinate of a photon
         *
         * @param[in] i Index of desired photon (no bounds checking)
         * @returns x coordinate of photon
         */
        double getX(int i) const {return _x[i];}
        /**
         * @brief Access y coordinate of a photon
         *
         * @param[in] i Index of desired photon (no bounds checking)
         * @returns y coordinate of photon
         */
        double getY(int i) const {return _y[i];}
        /**
         * @brief Access flux of a photon
         *
         * @param[in] i Index of desired photon (no bounds checking)
         * @returns flux of photon
         */
        double getFlux(int i) const {return _flux[i];}
        /**
         * @brief Return sum of all photons' fluxes
         *
         * @returns flux of photon
         */
        double getTotalFlux() const;
        /**
         * @brief Rescale all photon fluxes so that total flux matches argument
         *
         * If current total flux is zero, no rescaling is done.
         *
         * @param[in] flux desired total flux of all photons.
         */
        void setTotalFlux(double flux);

        /**
         * @brief Rescale all photon fluxes by the given factor
         *
         * @param[in] scale Scaling factor for all fluxes
         */
        void scaleFlux(double scale);

        /**
         * @brief Extend this array with the contents of another.
         *
         * @param[in] rhs PhotonArray whose contents to append to this one.
         */
        void append(const PhotonArray& rhs);
        /**
         * @brief Convolve this array with another.
         *
         * Convolution of two arrays is defined as adding the coordinates on a photon-by-photon basis
         * and multiplying the fluxes on a photon-by-photon basis. Output photons' flux is renormalized
         * so that the expectation value of output total flux is product of two input totals, if
	 * the two photon streams are uncorrelated.
         *
         * @param[in] rhs PhotonArray to convolve with this one.  Must be same size.
         */
        void convolve(const PhotonArray& rhs);

        /**
         * @brief Convolve this array with another, shuffling the order in which photons are combined.
         *
         * Same convolution behavior as convolve(), but the order in which the photons are
	 * multiplied into the array is randomized to destroy any flux or position correlations.
         *
         * @param[in] rhs PhotonArray to convolve with this one.  Must be same size.
         * @param[in] ud  A UniformDeviate used to shuffle the input photons.
         */
        void convolveShuffle(const PhotonArray& rhs, UniformDeviate& ud);

#ifdef USE_IMAGES
        /**
         * @brief Add flux of photons to an image by binning into pixels.
         *
         * Photon in this PhotonArray are binned into the pixels of the input
         * Image and their flux summed into the pixels.  Image is assumed to represent 
         * surface brightness, so photons' fluxes are divided by image pixel area.
         * Photons past the edges of the image are discarded.
         *
         * @param[in] target the Image to which the photons' flux will be added.
         */
        void addTo(Image<float>& target);
#endif
    private:
        std::vector<double> _x;      // Vector holding x coords of photons
        std::vector<double> _y;      // Vector holding y coords of photons
        std::vector<double> _flux;   // Vector holding flux of photons
    };
    /** 
     * @brief An abstract base class representing all of the 2D surface brightness profiles that 
     * we know how to draw.
     *
     * Every SBProfile knows how to draw an Image<float> of itself in real and k space.  Each also
     * knows what is needed to prevent aliasing or truncation of itself when drawn.
     * **Note** that when you use the SBProfile::draw() routines you will get an image of 
     * **surface brightness** values in each pixel, not the flux that fell into the pixel.  To get
     * flux, you must multiply the image by (dx*dx).
     * drawK() routines are normalized such that I(0,0) is the total flux.
     * Currently we have the following possible implementations of SBProfile:
     * Basic shapes: SBBox, SBGaussian, SBExponential, SBAiry, SBSersic
     * SBLaguerre: Gauss-Laguerre expansion
     * SBDistort: affine transformation of another SBProfile
     * SBRotate: rotated version of another SBProfile
     * SBAdd: sum of SBProfiles
     * SBConvolve: convolution of other SBProfiles
     * SBInterpolatedImage: surface brightness profiles defined by an image and interpolant.
     * SBDeconvolve: deconvolve one SBProfile with another
     */
    class SBProfile 
    {
    protected:
        static const int MINIMUM_FFT_SIZE;///< Constant giving minimum FFT size we're willing to do.
        static const int MAXIMUM_FFT_SIZE;///< Constant giving maximum FFT size we're willing to do.
        /**
         * @brief A rough indicator of how good the FFTs need to be for setting `maxK()` and 
         * `stepK()` values.
         */
        static const double ALIAS_THRESHOLD;

    public:

        /** 
         * @brief Destructor (virtual) -- Constructor and Copy Constructor are automatically 
         * generated by compiler.
         */
        virtual ~SBProfile() {}                        

        //
        // implementation-dependent methods
        //

        /// @brief Return a copy of self.
        virtual SBProfile* duplicate() const =0;

        /** 
         * @brief Return value of SBProfile at a chosen 2D position in real space.
         *
         * Assume all are real-valued.  xValue() may not be implemented for derived classes 
         * (SBConvolve) that require an FFT to determine real-space values.  In this case, an 
         * SBError will be thrown.
         *
         * @param[in] _p 2D position in real space.
         */
        virtual double xValue(Position<double> _p) const =0;

        /**
         * @brief Return value of SBProfile at a chosen 2D position in k space.
         *
         * @param[in] _p 2D position in k space.
         */
        virtual std::complex<double> kValue(Position<double> _p) const =0; 

        virtual double maxK() const =0; ///< Value of k beyond which aliasing can be neglected.

        /// @brief Image pixel spacing that does not alias maxK.
        virtual double nyquistDx() const { return M_PI / maxK(); }

        /**
         * @brief Sampling in k space necessary to avoid folding of image in x space.
         *
         * (TODO: Ensure that derived classes get additional info as needed).
         */
        virtual double stepK() const =0;

        /**
         *  @brief Characteristic that can affect efficiency of evaluation.
         *
         * (TODO: Ensure that derived classes get additional info as needed).
         */
        virtual bool isAxisymmetric() const =0;

        /** 
         * @brief Characteristic that can affect efficiency of evaluation.
         *
         * SBProfile is "analytic" in the real domain if values can be determined immediately at 
         * any position through formula or a stored table (no DFT).
         * (TODO: Ensure that derived classes get additional info as needed).
         */
        virtual bool isAnalyticX() const =0; 

        /**
         * @brief Characteristic that can affect efficiency of evaluation.
         * 
         * SBProfile is "analytic" in the k domain if values can be determined immediately at any 
         * position through formula or a stored table (no DFT).
         * (TODO: Ensure that derived classes get additional info as needed).
         */
        virtual bool isAnalyticK() const =0; 

        /// @brief Returns (X, Y) centroid of SBProfile.
        virtual Position<double> centroid() const = 0;

        virtual double getFlux() const =0; ///< Get the total flux of the SBProfile.

        /// @brief Set the total flux of the SBProfile
        //
        /// @param[in] flux_ flux
        virtual void setFlux(double flux_=1.) =0;

        // ****Methods implemented in base class****

        // Transformations (all are special cases of affine transformations via SBDistort):

        /**
         * @brief Ellipse distortion transformation (affine without rotation).
         *
         * This returns a pointer to a new SBProfile that represents a new Surface Brightness 
         * Profile with the requested transformation.  The type of the new object is currently 
         * SBDistort, but that is an implementation choice, and should not be assumed.
         * @param[in] e Ellipse class distortion.
         */
        virtual SBProfile* distort(const Ellipse e) const; 

        /** 
         * @brief Shear distortion transformation (affine without rotation or dilation).
         *           
         * This returns a pointer to a new SBProfile that represents a new Surface Brightness 
         * Profile with the requested transformation.  The type of the new object is currently 
         * SBDistort, but that is an implementation choice, and should not be assumed.
         * @param[in] e1 first component of ellipticity.
         * @param[in] e2 second component of ellipticity.
         */
        virtual SBProfile* shear(double e1, double e2) const { return distort(Ellipse(e1,e2)); }

        /** 
         * @brief Rotation distortion transformation.
         *
         * This returns a pointer to a new SBProfile that represents a new Surface Brightness 
         * Profile with the requested transformation.  The type of the new object is currently 
         * SBDistort, but that is an implementation choice, and should not be assumed.
         * @param[in] theta rotation, in radians, anticlockwise.
         */
        virtual SBProfile* rotate(const double theta) const;

        /**
         * @brief Translation transformation.
         *
         * This returns a pointer to a new SBProfile that represents a new Surface Brightness 
         * Profile with the requested transformation.  The type of the new object is currently 
         * SBDistort, but that is an implementation choice, and should not be assumed.
         * @param[in] dx shift in x.
         * @param[in] dy shift in y.
         */
        virtual SBProfile* shift(double dx, double dy) const;

        /**
         * @brief Shoot photons through this SBProfile.
         *
         * Returns an array of photon coordinates and fluxes that are drawn from the light
         * distribution of this SBProfile.  Absolute value of each photons' flux should be 
         * approximately equal, but some can be negative as needed to represent negative regions.
         * Note that the ray-shooting method is not intended to produce a randomized value of the total
         * object flux, so do not assume that there will be sqrt(N) error on the flux.  In fact 
         * most implementations will return a PhotonArray with exactly correct flux, with only
         * the *distribution* of flux on the sky that will definitely have sampling noise. 
         *
         * The one definitive gaurantee is that, in the limit of large number of photons, the surface 
         * brightness distribution of the photons will converge on the SB pattern defined by the object.
         *
         * Objects with regions of negative flux will result in creation of photons with negative flux. 
         * Absolute value of negative photons' flux should be nearly equal to the standard flux
         * of positive photons.  Shot-noise fluctuations between the number of positive and negative photons
         * will produce noise in the total net flux carried by the output [PhotonArray](@ref PhotonArray).
         *
         * @param[in] N Total umber of photons to produce.
         * @param[in] u UniformDeviate that will be used to draw photons from distribution.
         * @returns PhotonArray containing all the photons' info.
         */
        virtual PhotonArray shoot(int N, UniformDeviate& u) const=0;

        /**
         * @brief Return expectation value of flux in positive photons when shoot() is called
         *
         * Returns expectation value of flux returned in positive-valued photons when 
         * [shoot()](@ref shoot)
         * is called for this object.  Default implementation is to return getFlux(), if it is
         * positive, or 0 otherwise, which will be
         * the case when the SBProfile is constructed entirely from elements of the same sign.
         * @returns Expected positive-photon flux.
         */
        virtual double getPositiveFlux() const {return getFlux()>0. ? getFlux() : 0.;}

        /**
         * @brief Return expectation value of absolute value of flux in negative photons from shoot()
         *
         * Returns expectation value of (absolute value of) flux returned in positive-valued photons
         * when shoot() is called for this object.  Default implementation is to return getFlux() if it
         * is negative, 0 otherwise,
         * which will be the case when the SBProfile is constructed entirely from elements that
         * have the same sign.
         * @returns Expected absolute value of negative-photon flux.
         */
        virtual double getNegativeFlux() const {return getFlux()>0. ? 0. : -getFlux();}

#ifdef USE_IMAGES
        // **** Drawing routines ****
        /**
         * @brief Draw this SBProfile into Image by shooting photons.
         *
         * The input image must have defined boundaries and pixel scale.  The photons generated
         * by shoot() method will be binned into the target Image.  See caveats in shoot() docstring.
         * Input image will be cleared before drawing in the photons.
         * @param[in] img Image to draw on.
         * @param[in] N Total umber of photons to produce.
         * @param[in] u UniformDeviate that will be used to draw photons from distribution.
         */
        virtual void drawShoot(Image<float>& img, int N, UniformDeviate& u) const;

        /** 
         * @brief Draw an image of the SBProfile in real space.
         *
         * A square image will be
         * drawn which is big enough to avoid "folding."  If drawing is done using FFT,
         * it will be scaled up to a power of 2, or 3x2^n, whichever fits.
         * If input image has finite dimensions then these will be used, although in an FFT the 
         * image  may be calculated internally on a larger grid to avoid folding.
         * The default draw() routines decide internally whether image can be drawn directly
         * in real space or needs to be done via FFT from k space.
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in] dx    grid on which SBProfile is drawn has pitch `dx`; given `dx=0.` default, 
         *                  routine will choose `dx` to be at least fine enough for Nyquist sampling
         *                  at `maxK()`.  If you specify dx, image will be drawn with this `dx` and
         *                  you will receive an image with the aliased frequencies included.
         * @param[in] wmult specifying `wmult>1` will draw an image that is `wmult` times larger 
         *                  than the default choice, i.e. it will have finer sampling in k space 
         *                  and have less folding.
         * @returns image (as ImageF; if another type is preferred, then use the draw method that
         *                  takes an image as argument)
         */
        Image<float> draw(double dx=0., int wmult=1) const;

        /** 
         * @brief Draw the SBProfile in real space returning the summed flux.
         *
         * If on input image `img` is not specified or has null dimension, a square image will be
         * drawn which is big enough to avoid "folding."  If drawing is done using FFT,
         * it will be scaled up to a power of 2, or 3x2^n, whicher fits.
         * If input image has finite dimensions then these will be used, although in an FFT the 
         * image may be calculated internally on a larger grid to avoid folding.
         * The default draw() routines decide internally whether image can be drawn directly
         * in real space or needs to be done via FFT from k space.
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in,out]   image (any of ImageF, ImageD, ImageS, ImageI)
         * @param[in] dx    grid on which SBProfile is drawn has pitch `dx`; given `dx=0.` default, 
         *                  routine will choose `dx` to be at least fine enough for Nyquist sampling
         *                  at `maxK()`.  If you specify dx, image will be drawn with this `dx` and
         *                  you will receive an image with the aliased frequencies included.
         * @param[in] wmult specifying `wmult>1` will draw an image that is `wmult` times larger 
         *                  than the default choice, i.e. it will have finer sampling in k space 
         *                  and have less folding.
         * @returns summed flux.
         */
        template <typename T>
        double draw(Image<T> & image, double dx=0., int wmult=1) const; 

        /** 
         * @brief Draw an image of the SBProfile in real space forcing the use of real methods 
         * where we have a formula for x values.
         *
         * If on input image `img` is not specified or has null dimension, a square image will be
         * drawn which is big enough to avoid "folding." 
         * If input image has finite dimensions then these will be used, although in an FFT the 
         * image may be calculated internally on a larger grid to avoid folding.
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in,out]   image (any of ImageF, ImageD, ImageS, ImageI)
         * @param[in] dx    grid on which SBProfile is drawn has pitch `dx`; given `dx=0.` default, 
         *                  routine will choose `dx` to be at least fine enough for Nyquist sampling
         *                  at `maxK()`.  If you specify dx, image will be drawn with this `dx` and
         *                  you will receive an image with the aliased frequencies included.
         * @param[in] wmult specifying `wmult>1` will draw an image that is `wmult` times larger 
         *                  than the default choice, i.e. it will have finer sampling in k space 
         *                  and have less folding.
         * @returns summed flux.
         */
        template <typename T>
        double plainDraw(Image<T> & image, double dx=0., int wmult=1) const; 

        /** 
         * @brief Draw an image of the SBProfile in real space forcing the use of Fourier transform
         * from k space.
         *
         * If on input image `img` is not specified or has null dimension, a square image will be
         * drawn which is big enough to avoid "folding."  Drawing is done using FFT,
         * and the image will be scaled up to a power of 2, or 3x2^n, whicher fits.
         * If input image has finite dimensions then these will be used, although in an FFT the 
         * image may be calculated internally on a larger grid to avoid folding.
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in,out]   image (any of ImageF, ImageD, ImageS, ImageI)
         * @param[in] dx    grid on which SBProfile is drawn has pitch `dx`; given `dx=0.` default, 
         *                  routine will choose `dx` to be at least fine enough for Nyquist sampling
         *                  at `maxK()`.  If you specify dx, image will be drawn with this `dx` and
         *                  you will receive an image with the aliased frequencies included.
         * @param[in] wmult specifying `wmult>1` will draw an image that is `wmult` times larger 
         *                  than the default choice, i.e. it will have finer sampling in k space 
         *                  and have less folding.
         * @returns summed flux.
         */
        template <typename T>
        double fourierDraw(Image<T> & image, double dx=0., int wmult=1) const; 

        /** 
         * @brief Draw an image of the SBProfile in k space.
         *
         * For drawing in k space: routines are analagous to real space, except 2 images are 
         * needed since the SBProfile is complex.
         * If on input either image `Re` or `Im` is not specified or has null dimension, square 
         * images will be drawn which are big enough to avoid "folding."  If drawing is done using 
         * FFT, they will be scaled up to a power of 2, or 3x2^n, whicher fits.
         * If input image has finite dimensions then these will be used, although in an FFT the 
         * image may be calculated internally on a larger grid to avoid folding in real space.
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in,out]   re image of real argument of SBProfile in k space (any of ImageF,
         *                  ImageD, ImageS, ImageI). 
         * @param[in,out]   im image of imaginary argument of SBProfile in k space (any of ImageF,
         *                  ImageD, ImageS, ImageI).
         * @param[in] dk    grid on which SBProfile is drawn has pitch `dk`; given `dk=0.` default,
         *                  routine will choose `dk` necessary to avoid folding of image in real 
         *                  space.  If you specify `dk`, image will be drawn with this `dk` and
         *                  you will receive an image with folding artifacts included.
         * @param[in] wmult specifying `wmult>1` will expand the size drawn in k space.
         */
        template <typename T>
        void drawK(Image<T> & re, Image<T> & im, double dk=0., int wmult=1) const; 

        /** 
         * @brief Draw an image of the SBProfile in k space forcing the use of k space methods 
         * where we have a formula for k values.
         *
         * For drawing in k space: routines are analagous to real space, except 2 images are 
         * needed since the SBProfile is complex.  If on input either image `Re` or `Im` is not 
         * specified or has null dimension, square images will be drawn which are big enough to 
         * avoid "folding."
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in,out]   re image of real argument of SBProfile in k space (any of ImageF,
         *                  ImageD, ImageS, ImageI).
         * @param[in,out]   im image of imaginary argument of SBProfile in k space (any of ImageF,
         *                  ImageD, ImageS, ImageI).
         * @param[in] dk    grid on which SBProfile is drawn has pitch `dk`; given `dk=0.` default,
         *                  routine will choose `dk` necessary to avoid folding of image in real 
         *                  space.  If you specify `dk`, image will be drawn with this `dk` and
         *                  you will receive an image with folding artifacts included.
         * @param[in] wmult specifying `wmult>1` will expand the size drawn in k space.
         */
        template <typename T>
        void plainDrawK(Image<T> & re, Image<T> & im, double dk=0., int wmult=1) const; 

        /**
         * @brief Draw an image of the SBProfile in k space forcing the use of Fourier transform 
         * from real space.
         *
         * For drawing in k space: routines are analagous to real space, except 2 images are 
         * needed since the SBProfile is complex.
         * If on input either image `Re` or `Im` is not specified or has null dimension, square 
         * images will be drawn which are big enough to avoid "folding."  Drawing is done using FFT,
         * and the images will be scaled up to a power of 2, or 3x2^n, whicher fits.
         * If input image has finite dimensions then these will be used, although in an FFT the 
         * image may be calculated internally on a larger grid to avoid folding in real space.
         * Note that if you give an input image, its origin may be redefined by the time it comes 
         * back.
         *
         * @param[in,out]   re image of real argument of SBProfile in k space (any of ImageF,
         *                  ImageD, ImageS, ImageI).
         * @param[in,out]   im image of imaginary argument of SBProfile in k space (any of ImageF,
         *                  ImageD, ImageS, ImageI).
         * @param[in] dk    grid on which SBProfile is drawn has pitch `dk`; given `dk=0.` default,
         *                  routine will choose `dk` necessary to avoid folding of image in real 
         *                  space.  If you specify `dk`, image will be drawn with this `dk` and
         *                  you will receive an image with folding artifacts included.
         * @param[in] wmult specifying `wmult>1` will expand the size drawn in k space.
         */
        template <typename T>
        void fourierDrawK(Image<T> & re, Image<T> & im, double dk=0., int wmult=1) const; 

        /** 
         * @brief Utility for drawing into Image data structures.
         *
         * @param[out] image    image to fill (any of ImageF, ImageD, ImageS, ImageI).
         * @param[in]  dx       grid pitch on which SBProfile image is drawn
         */
        template <typename T>
        double fillXImage(Image<T> & image, double dx) const  // return flux integral
        { return doFillXImage(image, dx); }
#endif

        /**
         * @brief Utility for drawing a k grid into FFT data structures - not intended for public 
         * use, but need to be public so that derived classes can call them.
         */
        virtual void fillKGrid(KTable& kt) const;

        /** 
         * @brief Utility for drawing an x grid into FFT data structures - not intended for public 
         * use, but need to be public so that derived classes can call them.
         */
        virtual void fillXGrid(XTable& xt) const;

    protected:

#ifdef USE_IMAGES
        // Virtual functions cannot be templates, so to make fillXImage work like a virtual
        // function, we have it call these, which need to include all the types of Image
        // that we want to use.
        //
        // Then in the derived class, these functions should call a template version of 
        // fillXImage in that derived class that implements the functionality you want.
        virtual double doFillXImage(Image<float> & image, double dx) const
        { return doFillXImage2(image,dx); }
        virtual double doFillXImage(Image<double> & image, double dx) const
        { return doFillXImage2(image,dx); }

        // Here in the base class, we need yet another name for the version that actually
        // implements this as a template:
        template <typename T>
        double doFillXImage2(Image<T>& image, double dx) const;
#endif
    };

    /** 
     * @brief Sums SBProfiles. 
     *
     * Note that this class stores duplicates of its summands,
     * so they cannot be changed after adding them.
     */
    class SBAdd : public SBProfile 
    {
    protected:
        /// @brief The plist content is a pointer to a fresh copy of the summands.
        std::list<SBProfile*> plist; 
    private:
        double sumflux; ///< Keeps track of the cumulated flux of all summands.
        double sumfx; ///< Keeps track of the cumulated `fx` of all summands.
        double sumfy; ///< Keeps track of the cumulated `fy` of all summands.
        double maxMaxK; ///< Keeps track of the cumulated `maxK()` of all summands.
        double minStepK; ///< Keeps track of the cumulated `minStepK()` of all summands.

        /// @brief Keeps track of the cumulated `isAxisymmetric()` properties of all summands.
        bool allAxisymmetric;

        /// @brief Keeps track of the cumulated `isAnalyticX()` property of all summands. 
        bool allAnalyticX; 

        /// @brief Keeps track of the cumulated `isAnalyticK()` properties of all summands.
        bool allAnalyticK; 

        void initialize();  ///< Sets all private book-keeping variables to starting state.

    public:
        /// @brief Constructor, empty.
        SBAdd() : plist() { initialize(); }

        /** 
         * @brief Constructor, 1 input.
         *
         * @param[in] s1 SBProfile.
         */
        SBAdd(const SBProfile& s1) : plist() { initialize(); add(s1); }

        /** @brief Constructor, 2 inputs.
         *
         * @param[in] s1 first SBProfile.
         * @param[in] s2 second SBProfile.
         */
        SBAdd(const SBProfile& s1, const SBProfile& s2) : plist() 
        { initialize(); add(s1);  add(s2); }

        /** 
         * @brief Constructor, list of inputs.
         *
         * @param[in] slist list of SBProfiles.
         */
        SBAdd(const std::list<SBProfile*> slist) : plist() 
        {
            initialize();
            std::list<SBProfile*>::const_iterator sptr;
            for (sptr = slist.begin(); sptr!=slist.end(); ++sptr)
                add(**sptr); 
        }

        /** 
         * @brief Copy constructor.
         * @param[in] rhs SBAdd to be copied.
         */
        SBAdd(const SBAdd& rhs) : 
            plist(), sumflux(rhs.sumflux), sumfx(rhs.sumfx),
            sumfy(rhs.sumfy), maxMaxK(rhs.maxMaxK), minStepK(rhs.minStepK), 
            allAxisymmetric(rhs.allAxisymmetric),
            allAnalyticX(rhs.allAnalyticX), allAnalyticK(rhs.allAnalyticK)  
        {
            std::list<SBProfile*>::const_iterator sbptr;
            for (sbptr = rhs.plist.begin(); sbptr!=rhs.plist.end(); ++sbptr)
                plist.push_back((*sbptr)->duplicate());
        }

        /** @brief Assignment
         *
         * @param[in] rhs SBAdd which this one will now be a copy of.
         * @return reference to this.
         */
        SBAdd& operator=(const SBAdd& rhs)
        {
            // Null operation if rhs is this
            if (&rhs == this) return *this;
            // Clean up previous stuff

            for (std::list<SBProfile*>::iterator pptr = plist.begin(); 
                 pptr!=plist.end(); 
                 ++pptr)  
                delete *pptr; 
            // New copies of all convolve-ees:
            plist.clear();
            std::list<SBProfile*>::const_iterator rhsptr;
            for (rhsptr = rhs.plist.begin(); rhsptr!=rhs.plist.end(); ++rhsptr)
                plist.push_back((*rhsptr)->duplicate()); 
            // And copy other configurations:
            sumflux = rhs.sumflux;
            sumfx = rhs.sumfx;
            sumfy = rhs.sumfy;
            maxMaxK = rhs.maxMaxK;
            minStepK = rhs.minStepK;
            allAxisymmetric = rhs.allAxisymmetric;
            allAnalyticX = rhs.allAnalyticX;
            allAnalyticK = rhs.allAnalyticK;
            return *this;
        }

        /// @brief Destructor.
        ~SBAdd() 
        { 
            std::list<SBProfile*>::iterator pptr;
            for (pptr = plist.begin(); pptr!=plist.end(); ++pptr)  delete *pptr; 
        }

        /** 
         * @brief SBAdd specific method for adding additional SBProfiles
         *
         * @param[in] rhs SBProfile.
         * @param[in] scale allows for rescaling flux by this factor.
         */
        void add(const SBProfile& rhs, double scale=1.);

        // Barney's note: the methods below are documented at the SBProfile level (I think)

        SBProfile* duplicate() const { return new SBAdd(*this); } 

        double xValue(Position<double> _p) const;

        std::complex<double> kValue(Position<double> _p) const;

        double maxK() const { return maxMaxK; }
        double stepK() const { return minStepK; }

        bool isAxisymmetric() const { return allAxisymmetric; }
        bool isAnalyticX() const { return allAnalyticX; }
        bool isAnalyticK() const { return allAnalyticK; }

        virtual Position<double> centroid() const 
        {Position<double> p(sumfx / sumflux, sumfy / sumflux); return p; }

        virtual double getFlux() const { return sumflux; }
        virtual void setFlux(double flux_=1.);

        /**
         * @brief Shoot photons through this SBAdd.
         *
         * SBAdd will divide the N photons among its summands with probabilities proportional
         * to their fluxes.  Note that the order of photons in output array will not be
         * random as different summands' outputs are simply concatenated.
         * @param[in] N Total umber of photons to produce.
         * @param[in] u UniformDeviate that will be used to draw photons from distribution.
         * @returns PhotonArray containing all the photons' info.
         */
        virtual PhotonArray shoot(int N, UniformDeviate& u) const;
        /**
         * @brief Give total positive flux of all summands
         *
         * Note that `getPositiveFlux()` return from SBAdd may not equal the integral of positive
         * regions of the image, because summands could have positive and negative regions cancelling
         * each other.
         * @returns Total positive flux of all summands
         */
        virtual double getPositiveFlux() const;
        /** @brief Give absolute value of total negative flux of all summands
         *
         * Note that `getNegativeFlux()` return from SBAdd may not equal the integral of negative
         * regions of the image, because summands could have positive and negative regions cancelling
         * each other.
         * @returns Absolute value of total negative flux of all summands
         */
        virtual double getNegativeFlux() const;

        // Overrides for better efficiency:
        virtual void fillKGrid(KTable& kt) const;
        virtual void fillXGrid(XTable& xt) const;
    };

    /**
     * @brief An affine transformation of another SBProfile.
     *
     * Stores a duplicate of its target.
     * Origin of original shape will now appear at `x0`.
     * Flux is NOT conserved in transformation - surface brightness is preserved.
     * We keep track of all distortions in a 2x2 matrix `M = [(A B), (C D)]` = [row1, row2] 
     * plus a 2-element Positon object `x0` for the shift.
     */
    class SBDistort : public SBProfile 
    {

    private:
        SBProfile* adaptee; ///< SBProfile being adapted/distorted
        double matrixA; ///< A element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
        double matrixB; ///< B element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
        double matrixC; ///< C element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
        double matrixD; ///< D element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
        // Calculate and save these:
        Position<double> x0;  ///< Centroid position.
        double absdet;  ///< Determinant (flux magnification) of `M` matrix.
        double invdet;  ///< Inverse determinant of `M` matrix.
        double major; ///< Major axis of ellipse produced from unit circle.
        double minor; ///< Minor axis of ellipse produced from unit circle.
        bool stillIsAxisymmetric; ///< Is output SBProfile shape still circular?

    private:
        /// @brief Initialize the SBDistort.
        void initialize();

        /** 
         * @brief Forward coordinate transform with `M` matrix.
         *
         * @param[in] p input position.
         * @returns transformed position.
         */
        Position<double> fwd(Position<double> p) const 
        {
            Position<double> out(matrixA*p.x+matrixB*p.y,matrixC*p.x+matrixD*p.y);
            return out; 
        }

        /// @brief Forward coordinate transform with transpose of `M` matrix.
        Position<double> fwdT(Position<double> p) const 
        {
            Position<double> out(matrixA*p.x+matrixC*p.y,matrixB*p.x+matrixD*p.y);
            return out; 
        }

        /// @brief Inverse coordinate transform with `M` matrix.
        Position<double> inv(Position<double> p) const 
        {
            Position<double> out(invdet*(matrixD*p.x-matrixB*p.y),
                                 invdet*(-matrixC*p.x+matrixA*p.y));
            return out; 
        }

        /// @brief Returns the the k value (no phase).
        std::complex<double> kValNoPhase(Position<double> k) const 
        { return absdet*adaptee->kValue(fwdT(k)); }


    public:
        /** 
         * @brief General constructor.
         *
         * @param[in] sbin SBProfile being distorted
         * @param[in] mA A element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
         * @param[in] mB B element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
         * @param[in] mC C element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
         * @param[in] mD D element of 2x2 distortion matrix `M = [(A B), (C D)]` = [row1, row2]
         * @param[in] x0_ 2-element (x, y) Position for the translational shift.
         */
        SBDistort(
            const SBProfile& sbin, double mA, double mB, double mC, double mD,
            Position<double> x0_=Position<double>(0.,0.));

        /** 
         * @brief Construct from an input Ellipse class object
         *
         * @param[in] sbin SBProfile being distorted.
         * @param[in] e_ Ellipse.
         */
        SBDistort(const SBProfile& sbin, const Ellipse e_=Ellipse());

        /** 
         * @brief Copy constructor
         *
         * @param[in] rhs SBProfile being copied.
         */
        SBDistort(const SBDistort& rhs) 
        {
            adaptee = rhs.adaptee->duplicate();
            matrixA = (rhs.matrixA); 
            matrixB = (rhs.matrixB); 
            matrixC = (rhs.matrixC);
            matrixD = (rhs.matrixD); 
            x0 = (rhs.x0);
            initialize();
        }

        /** 
         * @brief Assignment operator
         *
         * @param[in] rhs SBDistort being copied.
         * @return   reference to this object.
         */
        SBDistort& operator=(const SBDistort& rhs) 
        {
            // Self-assignment is nothing:
            if (&rhs == this) return *this;
            if (adaptee) {delete adaptee; adaptee=0; }
            adaptee = rhs.adaptee->duplicate();
            matrixA = (rhs.matrixA); 
            matrixB = (rhs.matrixB); 
            matrixC = (rhs.matrixC);
            matrixD = (rhs.matrixD); 
            x0 = (rhs.x0);
            initialize();
            return *this;
        }

        /// @brief Destructor.
        ~SBDistort() { delete adaptee; adaptee=0; }

        // methods doxy described in base clase SBProfile
        SBProfile* duplicate() const 
        { return new SBDistort(*this); } 

        double xValue(Position<double> p) const 
        { return adaptee->xValue(inv(p-x0)); }

        std::complex<double> kValue(Position<double> k) const 
        {
            std::complex<double> phaseexp(0,-k.x*x0.x-k.y*x0.y); // phase exponent
            std::complex<double> kv(absdet*adaptee->kValue(fwdT(k))*std::exp(phaseexp));
            return kv; 
        }

        bool isAxisymmetric() const { return stillIsAxisymmetric; }
        bool isAnalyticX() const { return adaptee->isAnalyticX(); }
        bool isAnalyticK() const { return adaptee->isAnalyticK(); }

        double maxK() const { return adaptee->maxK() / minor; }
        double stepK() const { return adaptee->stepK() / major; }

        Position<double> centroid() const { return x0+fwd(adaptee->centroid()); }

        double getFlux() const { return adaptee->getFlux()*absdet; }
        void setFlux(double flux_=1.) { adaptee->setFlux(flux_/absdet); }

        double getPositiveFlux() const {return adaptee->getPositiveFlux()*absdet;}
        double getNegativeFlux() const {return adaptee->getNegativeFlux()*absdet;}

        /**
         * @brief Shoot photons through this SBDistort.
         *
         * SBDistort will simply apply the affine distortion to coordinates of photons
         * generated by its adaptee.
         * @param[in] N Total umber of photons to produce.
         * @param[in] u UniformDeviate that will be used to draw photons from distribution.
         * @returns PhotonArray containing all the photons' info.
         */
        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        void fillKGrid(KTable& kt) const; // optimized phase calculation
    };

    /**
     * @brief Convolve SBProfiles.
     *
     * Convolve one, two, three or more SBProfiles together (TODO: Add a more detailed description
     * here).
     */
    class SBConvolve : public SBProfile 
    {
    private:
        /// @brief The plist content is a copy_ptr (cf. smart ptrs) listing SBProfiles.
        std::list<SBProfile*> plist;

        double fluxScale; ///< Flux scaling.
        double x0; ///< Centroid position in x.
        double y0; ///< Centroid position in y.
        bool isStillAxisymmetric; ///< Is output SBProfile shape still circular?
        double minMaxK; ///< Minimum maxK() of the convolved SBProfiles.
        double minStepK; ///< Minimum stepK() of the convolved SBProfiles.
        double fluxProduct; ///< Flux of the product.

    public:
        /// @brief Constructor, empty.
        SBConvolve() : plist(), fluxScale(1.) {} 

        /**
         * @brief Constructor, 1 input.
         *
         * @param[in] s1 SBProfile.
         * @param[in] f scaling factor for final flux (default `f = 1.`).
         */
        SBConvolve(const SBProfile& s1, double f=1.) : plist(), fluxScale(f) 
        { add(s1); }

        /**
         * @brief Constructor, 2 inputs.
         *
         * @param[in] s1 first SBProfile.
         * @param[in] s2 second SBProfile.
         * @param[in] f scaling factor for final flux (default `f = 1.`).
         */
        SBConvolve(const SBProfile& s1, const SBProfile& s2, double f=1.) : 
            plist(), fluxScale(f) 
        { add(s1);  add(s2); }

        /**
         * @brief Constructor, 3 inputs.
         *
         * @param[in] s1 first SBProfile.
         * @param[in] s2 second SBProfile.
         * @param[in] s3 third SBProfile.
         * @param[in] f scaling factor for final flux (default `f = 1.`).
         */
        SBConvolve(
            const SBProfile& s1, const SBProfile& s2, const SBProfile& s3, double f=1.) :
            plist(), fluxScale(f) 
        { add(s1);  add(s2);  add(s3); }

        /**
         * @brief Constructor, list of inputs.
         *
         * @param[in] slist Input: list of SBProfiles.
         * @param[in] f Input: optional scaling factor for final flux (default `f = 1.`).
         */
        SBConvolve(const std::list<SBProfile*> slist, double f=1.) :
            plist(), fluxScale(f) 
        { 
            std::list<SBProfile*>::const_iterator sptr;
            for (sptr = slist.begin(); sptr!=slist.end(); ++sptr) add(**sptr); 
        }

        /** @brief Copy constructor.
         *
         * @param[in] rhs SBProfile.
         */
        SBConvolve(const SBConvolve& rhs) : 
            plist(), fluxScale(rhs.fluxScale),
            x0(rhs.x0), y0(rhs.y0),
            isStillAxisymmetric(rhs.isStillAxisymmetric),
            minMaxK(rhs.minMaxK), minStepK(rhs.minStepK),
            fluxProduct(rhs.fluxProduct) 
        {
            std::list<SBProfile*>::const_iterator rhsptr;
            for (rhsptr = rhs.plist.begin(); rhsptr!=rhs.plist.end(); ++rhsptr)
                plist.push_back((*rhsptr)->duplicate()); 
        }

        /** @brief Assignment
         *
         * @param[in] rhs SBConvolve which this one will now be a copy of.
         * @return reference to this.
         */
        SBConvolve& operator=(const SBConvolve& rhs)
        {
            // Null operation if rhs is this
            if (&rhs == this) return *this;
            // Clean up previous stuff

            for (std::list<SBProfile*>::iterator pptr = plist.begin(); 
                 pptr!=plist.end(); 
                 ++pptr)  
                delete *pptr; 
            // New copies of all convolve-ees:
            plist.clear();
            std::list<SBProfile*>::const_iterator rhsptr;
            for (rhsptr = rhs.plist.begin(); rhsptr!=rhs.plist.end(); ++rhsptr)
                plist.push_back((*rhsptr)->duplicate()); 
            // And copy other configurations:
            fluxScale = rhs.fluxScale;
            x0 = rhs.x0;
            y0 = rhs.y0;
            isStillAxisymmetric = rhs.isStillAxisymmetric;
            minMaxK = rhs.minMaxK;
            minStepK = rhs.minStepK;
            fluxProduct = rhs.fluxProduct;
            return *this;
        }

        /// @brief Destructor.
        ~SBConvolve() 
        { 
            std::list<SBProfile*>::iterator pptr;
            for (pptr = plist.begin(); pptr!=plist.end(); ++pptr)  delete *pptr; 
        }

        /** 
         * @brief SBConvolve specific method for adding new members.
         *
         * @param rhs Input: SBProfile for adding.
         */
        void add(const SBProfile& rhs); 

        // Barney's note: I think the methods below are documented at the SBProfile level

        // implementation dependent methods:
        SBProfile* duplicate() const { return new SBConvolve(*this); } 

        double xValue(Position<double> _p) const 
        { throw SBError("SBConvolve::xValue() not allowed"); } 

        std::complex<double> kValue(Position<double> k) const 
        {
            std::list<SBProfile*>::const_iterator pptr;
            std::complex<double> product(fluxScale,0);
            for (pptr=plist.begin(); pptr!=plist.end(); ++pptr)
                product *= (*pptr)->kValue(k);
            return product; 
        }

        bool isAxisymmetric() const { return isStillAxisymmetric; }
        bool isAnalyticX() const { return false; }
        bool isAnalyticK() const { return true; }    // convolvees must all meet this
        double maxK() const { return minMaxK; }
        double stepK() const { return minStepK; }

        Position<double> centroid() const 
        { Position<double> p(x0, y0); return p; }

        double getFlux() const { return fluxScale * fluxProduct; }
        void setFlux(double flux_=1.) { fluxScale = flux_/fluxProduct; }

        double getPositiveFlux() const;
        double getNegativeFlux() const;
        /**
         * @brief Shoot photons through this SBConvolve.
         *
         * SBConvolve will add the displacements of photons generated by each convolved component.
         * @param[in] N Total umber of photons to produce.
         * @param[in] u UniformDeviate that will be used to draw photons from distribution.
         * @returns PhotonArray containing all the photons' info.
         */
        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        // Overrides for better efficiency:
        virtual void fillKGrid(KTable& kt) const;
    };

    /**
     * @brief Gaussian Surface Brightness Profile
     *
     * The Gaussian Surface Brightness Profile is characterized by two properties, its `flux`
     * and the characteristic size `sigma` where the radial profile of the circular Gaussian
     * drops off as `exp[-r^2 / (2. * sigma^2)]`.
     * The maxK() and stepK() are for the SBGaussian are chosen to extend to 4 sigma in both 
     * real and k domains, or more if needed to reach the `ALIAS_THRESHOLD` spec.
     */
    class SBGaussian : public SBProfile 
    {
    private:
        double flux; ///< Flux of the Surface Brightness Profile.

        /// @brief Characteristic size, surface brightness scales as `exp[-r^2 / (2. * sigma^2)]`.
        double sigma;

    public:
        /** 
         * @brief Constructor.
         *
         * @param[in] flux_  flux of the Surface Brightness Profile (default `flux_ = 1.`).
         * @param[in] sigma_ characteristic size, surface brightness scales as 
         *                   `exp[-r^2 / (2. * sigma^2)] (default `sigma_ = 1.`).
         */
        SBGaussian(double flux_=1., double sigma_=1.) : flux(flux_), sigma(sigma_) {}

        /// @brief Destructor.
        ~SBGaussian() {}                        

        double xValue(Position<double> _p) const;
        std::complex<double> kValue(Position<double> _p) const;

        bool isAxisymmetric() const { return true; } 
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }

        // Extend to 4 sigma in both domains, or more if needed to reach EE spec
        double maxK() const { return std::max(4., std::sqrt(-2.*log(ALIAS_THRESHOLD))) / sigma; }
        double stepK() const 
        { return M_PI/std::max(4., std::sqrt(-2.*log(ALIAS_THRESHOLD))) / sigma; }
        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }

        double getFlux() const { return flux; }
        void setFlux(double flux_=1.) { flux=flux_; }
        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        SBProfile* duplicate() const { return new SBGaussian(*this); }
    };

    /**
     * @brief Sersic Surface Brightness Profile.
     *
     * The Sersic Surface Brightness Profile is characterized by three properties: its Sersic 
     * index `n`, its `flux` and the half-light radius `re`.
     */
    class SBSersic : public SBProfile 
    {
    private:
        /// @brief A private class that caches the needed parameters for each Sersic index `n`.
        class SersicInfo 
        {
        public:
            /** 
             * @brief This class contains all the info needed to calculate values for a given 
             * Sersic index `n`.
             */
            SersicInfo(double n); 
            double inv2n;   ///< `1 / (2 * n)`
            double maxK;    ///< Value of k beyond which aliasing can be neglected.
            double stepK;   ///< Sampling in k space necessary to avoid folding of image in x space.

            /** 
             * @brief Returns the real space value of the Sersic using the formula 
             * `exp(-b*pow(xsq,inv2n))` (see private attributes).
             */
            double xValue(double xsq) const { return norm*std::exp(-b*std::pow(xsq,inv2n)); } 

            /// @brief Looks up the k value for the SBProfile from a lookup table.
            double kValue(double ksq) const;

        private:
            SersicInfo(const SersicInfo& rhs) {} ///< Hides the copy constructor.

            /** 
             * @brief Scaling in Sersic profile `exp(-b*pow(xsq,inv2n))`, calculated from Sersic 
             * index `n` and half-light radius `re`.
             */
            double b; 

            double norm; ///< Amplitude scaling in Sersic profile `exp(-b*pow(xsq,inv2n))`.
            double kderiv2; ///< Quadratic dependence near k=0.
            double kderiv4; ///< Quartic dependence near k=0.
            double logkMin; ///< Minimum log(k) in lookup table.
            double logkMax; ///< Maximum log(k) in lookup table.
            double logkStep; ///< Stepsize in log(k) in lookup table.
            std::vector<double> lookup; ///< Lookup table.
        };

        /** 
         * @brief A map to hold one copy of the SersicInfo for each `n` ever used during the 
         * program run.  Make one static copy of this map.
         */
        class InfoBarn : public std::map<double, const SersicInfo*> 
        {
        public:

            /**
             * @brief Get the SersicInfo table for a specified `n`.
             *
             * @param[in] n Sersic index for which the information table is required.
             */
            const SersicInfo* get(double n) 
            {
                /** 
                 * @brief The currently hardwired max number of Sersic `n` info tables that can be 
                 * stored.  Should be plenty.
                 */
                const int MAX_SERSIC_TABLES = 100; 

                const SersicInfo* info = (*this)[n];
                if (info==0) {
                    info = new SersicInfo(n);
                    (*this)[n] = info;
                    if (int(size()) > MAX_SERSIC_TABLES)
                        throw SBError("Storing Sersic info for too many n values");
                }
                return info;
            }
            /// @brief Destructor.
            ~InfoBarn() 
            {
                typedef std::map<double,const SersicInfo*>::iterator mapit;
                for (mapit pos = begin(); pos != end(); ++pos) {
                    delete pos->second;
                    pos->second = 0;
                }
            }
        };
        static InfoBarn nmap;

        // Now the parameters of this instance of SBSersic:
        double n; ///< Sersic index.
        double flux; ///< Flux.
        double re;   ///< Half-light radius.
        const SersicInfo* info; ///< Points to info structure for this n.

    public:
        /**
         * @brief Constructor.
         *
         * @param[in] n_    Sersic index.
         * @param[in] flux_ flux (default `flux_ = 1.`).
         * @param[in] re_   half-light radius (default `re_ = 1.`).
         */
        SBSersic(double n_, double flux_=1., double re_=1.) :
            n(n_), flux(flux_), re(re_), info(nmap.get(n)) {}

        // Default copy constructor should be fine.

        /// @brief Destructor.
        ~SBSersic() {}

        // Barney note: methods below already doxyfied via SBProfile, except for getN

        double xValue(Position<double> p) const 
        {
            p /= re;
            return flux*info->xValue(p.x*p.x+p.y*p.y) / (re*re);
        }

        std::complex<double> kValue(Position<double> k) const 
        {
            k *= re;
            return std::complex<double>( flux*info->kValue(k.x*k.x+k.y*k.y), 0.);
        }

        bool isAxisymmetric() const { return true; }
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }  // 1d lookup table

        double maxK() const { return info->maxK / re; }
        double stepK() const { return info->stepK / re; }

        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }

        double getFlux() const { return flux; }
        void setFlux(double flux_=1.) { flux=flux_; }

        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        SBProfile* duplicate() const { return new SBSersic(*this); }

        /// @brief A method that only works for Sersic, @returns the Sersic index `n`.
        double getN() const { return n; }
    };

    /** 
     * @brief Exponential Surface Brightness Profile.  
     *
     * This is a special case of the Sersic profile, but is given a separate class since the 
     * Fourier transform has closed form and can be generated without lookup tables.
     * The maxK() is set to where the FT is down to 0.001, or via `ALIAS_THRESHOLD`, whichever is 
     * harder.
     */
    class SBExponential : public SBProfile 
    {
    private:
        double r0;   ///< Characteristic size of profile `exp[-(r / r0)]`.
        double flux; ///< Flux.
    public:
        /** 
         * @brief Constructor - note that `r0` is scale length, NOT half-light radius `re` as in 
         * SBSersic.
         *
         * @param[in] flux_ flux (default `flux_ = 1.`).
         * @param[in] r0_   scale length for the profile that scales as `exp[-(r / r0)]`, NOT the 
         *                  half-light radius `re` as in SBSersic (default `r0_ = 1.`).
         */
        SBExponential(double flux_=1., double r0_=1.) : r0(r0_), flux(flux_) {}

        /// @brief Destructor.
        ~SBExponential() {}

        // Methods
        double xValue(Position<double> _p) const;
        std::complex<double> kValue(Position<double> _p) const;

        bool isAxisymmetric() const { return true; } 
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }

        // Set maxK where the FT is down to 0.001 or threshold, whichever is harder.
        double maxK() const { return std::max(10., pow(ALIAS_THRESHOLD, -1./3.))/r0; }
        double stepK() const;

        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }

        double getFlux() const { return flux; }
        void setFlux(double flux_=1.) { flux=flux_; }

        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        SBProfile* duplicate() const { return new SBExponential(*this); }
    };

    /** 
     * @brief Surface Brightness Profile for the Airy disk (perfect diffraction-limited PSF for a 
     * circular aperture), with central obscuration.
     *
     * maxK() is set at the hard limit for Airy disks, stepK() makes transforms go to at least 
     * 5 lam/D or EE>(1-ALIAS_THRESHOLD).  Schroeder (10.1.18) gives limit of EE at large radius.
     * This stepK could probably be relaxed, it makes overly accurate FFTs.
     * Note x & y are in units of lambda/D here.  Integral over area will give unity in this 
     * normalization.
     */
    class SBAiry : public SBProfile 
    {
    private:
        /** 
         * @brief `D` = (telescope diam) / (lambda * focal length) if arg is focal plane position, 
         * else `D` = (telescope diam) / lambda if arg is in radians of field angle.
         */
        double D; 

        double obscuration; ///< Radius ratio of central obscuration.
        double flux; ///< Flux.

    public:
        /** Brief Constructor.
         *
         * @param[in] D_    `D` = (telescope diam) / (lambda * focal length) if arg is focal plane 
         *                  position, else `D` = (telescope diam) / lambda if arg is in radians of 
         *                  field angle (default `D_ = 1.`).
         * @param[in] obs_  radius ratio of central obscuration (default `obs_ = 0.`).
         * @param[in] flux_ flux (default `flux_ = 1.`).
         */
        SBAiry(double D_=1., double obs_=0., double flux_=1.) :
            D(D_), obscuration(obs_), flux(flux_) {}

        /// @brief Destructor.
        ~SBAiry() {}

        // Methods (Barney: mostly described by SBProfile Doxys, with maxK() and stepK() 
        // prescription described in class description).
        double xValue(Position<double> _p) const;
        std::complex<double> kValue(Position<double> _p) const;

        bool isAxisymmetric() const { return true; } 
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }

        double maxK() const { return 2*M_PI*D; } ///< Set at hard limit for Airy disk.

        // stepK makes transforms go to at least 5 lam/D or EE>(1-ALIAS_THRESHOLD).
        // Schroeder (10.1.18) gives limit of EE at large radius.
        // This stepK could probably be relaxed, it makes overly accurate FFTs.
        double stepK() const 
        { 
            return std::min( 
                ALIAS_THRESHOLD * 0.5 * D * pow(M_PI,3.) * (1-obscuration) ,
                M_PI * D / 5.);
        }

        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }

        double getFlux() const { return flux; }
        void setFlux(double flux_=1.) { flux=flux_; }

        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        SBProfile* duplicate() const { return new SBAiry(*this); }

    private: 
        double chord(const double r, const double h) const; ///< Circle chord length at `h < r`.

        /// @brief Area inside intersection of 2 circles radii `r` & `s`, seperated by `t`.
        double circle_intersection(
            double r, double s, double t) const; 

        /// @brief Area of two intersecting identical annuli.
        double annuli_intersect(
            double r1, double r2, double t) const; 
        /** 
         * @brief Beam pattern of annular aperture, in k space, which is just the autocorrelation 
         * of two annuli.  Normalized to unity at `k=0` for now.
         */
        double annuli_autocorrelation(const double k) const; 
    };

    /** 
     * @brief Surface Brightness Profile for the Boxcar function.
     *
     * Convolution with a Boxcar function of dimensions `xw` x `yw` and sampling at pixel centres
     * is equivalent to pixelation (i.e. Surface Brightness integration) across rectangular pixels
     * of the same dimensions.  This class is therefore useful for pixelating SBProfiles.
     */ 
    class SBBox : public SBProfile 
    {
    private:
        double xw;   ///< Boxcar function is `xw` x `yw` across.
        double yw;   ///< Boxcar function is `xw` x `yw` across.
        double flux; ///< Flux.
        /** 
         * @brief Sinc function used to describe Boxcar in k space. 
         * @param[in] u Normalized wavenumber.
         */
        double sinc(const double u) const; 

    public:
        /** 
         * @brief Constructor.
         *
         * @param[in] xw_   width of Boxcar function along x (default `xw_ = 1.`).
         * @param[in] yw_   width of Boxcar function along y (default `yw_ = 0.`).
         * @param[in] flux_ flux (default `flux_ = 1.`).
         */
        SBBox(double xw_=1., double yw_=0., double flux_=1.) :
            xw(xw_), yw(yw_), flux(flux_) 
        { if (yw==0.) yw=xw; }

        /// @brief Destructor.
        ~SBBox() {}

        // Methods (Barney: public methods Doxified via SBProfile).
        double xValue(Position<double> _p) const;
        std::complex<double> kValue(Position<double> _p) const;

        bool isAxisymmetric() const { return false; } 
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }
 
       double maxK() const { return 2. / ALIAS_THRESHOLD / std::max(xw,yw); }  
        double stepK() const { return M_PI/std::max(xw,yw)/2; } 

        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }

        double getFlux() const { return flux; }
        void setFlux(double flux_=1.) { flux=flux_; }

        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        SBProfile* duplicate() const { return new SBBox(*this); }

        // Override to put in fractional edge values:
        void fillXGrid(XTable& xt) const;

        template <typename T>
        double fillXImage(Image<T>& I, double dx) const;

    protected:
#ifdef USE_IMAGES
        virtual double doFillXImage(Image<float>& I, double dx) const
        { return fillXImage(I,dx); }
        virtual double doFillXImage(Image<double>& I, double dx) const
        { return fillXImage(I,dx); }
        virtual double doFillXImage(Image<short>& I, double dx) const
        { return fillXImage(I,dx); }
        virtual double doFillXImage(Image<int>& I, double dx) const
        { return fillXImage(I,dx); }
#endif

    };

#ifdef USE_LAGUERRE
    /// @brief Class for describing Gauss-Laguerre polynomial Surface Brightness Profiles.
    class SBLaguerre : public SBProfile 
    {
    private:
        LVector bvec;  ///< `bvec[n,n]` contains flux information for the `(n, n)` basis function.
        double sigma;  ///< Scale size of Gauss-Laguerre basis set.
    public:
        /** 
         * @brief Constructor.
         *
         * @param[in] bvec_  `bvec[n,n]` contains flux information for the `(n, n)` basis function.
         * @param[in] sigma_ scale size of Gauss-Laguerre basis set (default `sigma_ = 1.`).
         */
        SBLaguerre(LVector bvec_=LVector(), double sigma_=1.) : 
            bvec(bvec_.duplicate()), sigma(sigma_) {}

        /// @brief Copy Constructor. 
        SBLaguerre(const SBLaguerre& rhs) :
            bvec(rhs.bvec.duplicate()), sigma(rhs.sigma) {}

        /// @brief Destructor. 
        ~SBLaguerre() {}

        // implementation dependent methods
        SBProfile* duplicate() const { return new SBLaguerre(*this); }

        double xValue(Position<double> _p) const;
        std::complex<double> kValue(Position<double> _p) const;

        double maxK() const;
        double stepK() const;

        bool isAxisymmetric() const { return false; }
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }

        Position<double> centroid() const 
        { throw SBError("SBLaguerre::centroid calculations not yet implemented"); }

        double getFlux() const;
        void setFlux(double flux_=1.);

        virtual PhotonArray shoot(int N, UniformDeviate& u) const {
            throw SBError("SBLaguerre::shoot() is not implemented");
        }

        // void fillKGrid(KTable& kt) const;
        // void fillXGrid(XTable& xt) const;

    };
#endif

    /**
     * @brief Surface Brightness for the Moffat Profile (an approximate description of ground-based
     * PSFs).
     */
    class SBMoffat : public SBProfile 
    {
    private:
        double beta; ///< Moffat beta parameter for profile `[1 + (r / rD)^2]^beta`.
        double flux; ///< Flux.
        double norm; ///< Normalization.
        double rD;   ///< Scale radius for profile `[1 + (r / rD)^2]^beta`.
        // In units of rD:
        double maxRrD; ///< Maximum `r` in units of `rD`.
        double maxKrD; ///< Maximum lookup table `k` in units of `rD`.
        double stepKrD; ///< Stepsize lookup table `k` in units of `rD`.
        double FWHMrD;  ///< Full Width at Half Maximum corresponding to `rD`.
        double rerD;    ///< Half-light radius corresponding to `rD`.

        Table<double,double> ft;  ///< Lookup table for Fourier transform of Moffat.

    public:
        /** @brief Constructor.
         *
         * @param[in] beta_          Moffat beta parameter for profile `[1 + (r / rD)^2]^beta`.
         * @param[in] truncationFWHM outer truncation in units of FWHM (default `truncationFWHM = 
         * 2.`).
         * @param[in] flux_          Flux (default `flux_ = 1.`).
         * @param[in] re             Half-light radius (default `re = 1.`).
         */
        SBMoffat(
            double beta_, double truncationFWHM=2., double flux_=1., double re=1.);

        // Default copy constructor should be fine.

        /// @brief Destructor.
        ~SBMoffat() {}

        double xValue(Position<double> p) const 
        {
            p /= rD;
            double rsq = p.x*p.x+p.y*p.y;
            if (rsq >= maxRrD*maxRrD) return 0.;
            else return flux*norm*pow(1+rsq, -beta) / (rD*rD);
        }

        std::complex<double> kValue(Position<double> k) const; 

        bool isAxisymmetric() const { return true; } 
        bool isAnalyticX() const { return true; }
        bool isAnalyticK() const { return true; }  // 1d lookup table

        double maxK() const { return maxKrD / rD; }   
        double stepK() const { return stepKrD / rD; } 

        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }


        double getFlux() const { return flux; }
        void setFlux(double flux_=1.) { flux=flux_; }

        virtual PhotonArray shoot(int N, UniformDeviate& u) const;

        SBProfile* duplicate() const { return new SBMoffat(*this); }

        // Methods that only work for Moffat:

        /// @brief Returns the Moffat beta parameter for profile `[1 + (r / rD)^2]^beta`.
        double getBeta() const { return beta; }

        /// @brief Set the FWHM. @param fwhm Input: new FWHM.
        void setFWHM(double fwhm) { rD = fwhm / FWHMrD; }

        /** 
         * @brief Set the Moffat scale radius for profile `[1 + (r / rD)^2]^beta`. 
         * @param rD_ Input: new `rD`.
         */
        void setRd(double rD_) { rD = rD_; }
    };


    /// @brief This class is for backwards compatibility; prefer rotate() method.
    class SBRotate : public SBDistort 
    {
    public:
        // constructor #1

        /** @brief Constructor.
         *
         * @param[in] s     SBProfile being rotated.
         * @param[in] theta Rotation angle in radians anticlockwise.
         */
        SBRotate(const SBProfile& s, const double theta) :
            SBDistort(s, std::cos(theta), -std::sin(theta), std::sin(theta), std::cos(theta)) {}
    };

    /**
     * @brief Surface Brightness for the de Vaucouleurs Profile, a special case of the Sersic with 
     * `n = 4`.
     */
    class SBDeVaucouleurs : public SBSersic 
    {
    public:
        /** 
         * @brief Constructor.
         *
         * @param[in] flux_ flux (default `flux_ = 1.`).
         * @param[in] r0_   Half-light radius (default `r0_ = 1.`).
         */
        SBDeVaucouleurs(double flux_=1., double r0_=1.) : SBSersic(4., flux_, r0_) {}

        /// @brief Destructor.
        ~SBDeVaucouleurs() {}

        /// @brief Copy constructor.
        SBProfile* duplicate() const { return new SBDeVaucouleurs(*this); }

        Position<double> centroid() const 
        { Position<double> p(0., 0.); return p; }


    };


}

#endif // SBPROFILE_H

