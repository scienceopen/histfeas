from pathlib import Path
import logging
from numpy import (
    s_,
    array,
    empty,
    empty_like,
    isnan,
    asfortranarray,
    linspace,
    outer,
    sin,
    cos,
    pi,
    ones_like,
    nan,
    unravel_index,
    meshgrid,
    logspace,
    log10,
    spacing,
    atleast_2d,
    ndarray,
)
from datetime import datetime

# from numpy.ma import masked_invalid #for pcolormesh, which doesn't like NaN
from matplotlib.pyplot import figure, subplots, text, colorbar
from matplotlib.colors import LogNorm
from matplotlib.ticker import (
    LogFormatterMathtext,
    MultipleLocator,
    ScalarFormatter,
)  # for 1e4 -> 1 x 10^4, applied DIRECTLY in format=
import h5py
from scipy.interpolate import interp1d
from xarray import DataArray

#
from .nans import nans

#
try:
    import plotly.plotly as py
    from plotly.graph_objs import Data, Figure, XAxis, YAxis, Contour, Layout
except ImportError:
    plotly = None
#
try:
    from gaussfitter import gaussfit, twodgaussian
except Exception as e:
    gaussfitter = None
#
from sciencedates import find_nearest
from histutils.plotsimul import plotRealImg, plotPlainImg
from gridaurora.opticalmod import plotOptMod
from gridaurora.plots import ploteigver, writeplots, nametime
from .io import planviewkml

#%% plot globals
longtitle = False
# pcmcmap = get_cmap('jet')
# pcmcmap.set_under('white')
dymaj = 100
dymin = 25
dxmax = 1.0
dxmin = 0.5
pstyle = "contour"

phi1dmax = 5e5

#%%
def logfmt(makeplot, powlim=(-2, 2)):
    """
    call this in EACH function--don't try to reuse or one plot will affect
    the other, particularly a problem with colorbar() (in matplotlib 1.4.2/1.4.3 at least)
    """
    if isinstance(makeplot, dict):
        makeplot = makeplot["makeplot"]

    cnorm = [None]
    sfmt = ScalarFormatter(useMathText=True)  # for 10^3 instead of 1e3
    sfmt.set_powerlimits(powlim)  # force scientific notation for numbers with 10^a where A<a<B
    sfmt.set_scientific(True)
    sfmt.set_useOffset(False)
    sfmt = [sfmt]
    if "log" in makeplot:  # it will plot log and linear!
        cnorm.append(LogNorm())
        sfmt.append(LogFormatterMathtext())
    return cnorm, sfmt


def placetxt(x, y, txt, ax):
    ax.text(
        x,
        y,
        txt,
        color="white",
        fontsize=45,
        va="bottom",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.0", fc="black", alpha=0.25),
    )


def goPlot(sim, Fwd, cam, Lfwd, Tm, drn, dhat, ver, vfit, Peig, Phi0, Phifit, rawdata, tInd, P):
    makeplot = P["makeplot"]
    #%% nicer file naming
    T = tind2dt(cam, tInd)
    #%% convenience
    # cord = ['b','g','k','r','m','y']
    xKM = Fwd["x"]
    zKM = Fwd["z"]
    xp = Fwd["xPixCorn"]
    zp = Fwd["zPixCorn"]
    sx = Fwd["sx"]
    sz = Fwd["sz"]

    nCutPix = sim.ncutpix  # FIXME assumes all cams same # of pixels

    #%% get xind
    Jxi = indone1d(xKM, P, tInd)
    #%% eigenfunction
    if "eig" in makeplot:
        ploteigver(Phifit["EKpcolor"], zKM, Tm, sim, T, P, "peig")

        # FIXME this is temporary hack until Peigen is passed to hist-feasibility as DataFrame
        Peigen = DataArray(
            data=Peig["Mp"], coords=[zKM, Phifit["EK"]], dims=["alt_km", "energy_ev"]
        )
        plotOptMod(None, Peigen)

        ploteig1d(Phifit["EK"], zKM, Tm, sim, T, P, "peig1d")

    if "tphi0" in makeplot:
        plottphi0(Tm, Phi0, Jxi, Phifit["EK"], zKM, sim, T, P, "tphi0")

    if "spectra" in makeplot:
        logging.warning("run spectral plots from calcemissions.py")
    #%% show video
    if "realvid" in makeplot and rawdata is not None:
        plotRealImg(sim, cam, rawdata, tInd, odir=P["outdir"])

    if "singleraw" in makeplot and rawdata is not None:
        plotPlainImg(sim, cam, rawdata, tInd, P["outdir"])
    #%% scatter plot of LOS
    if "kml" in makeplot or "kmlrays" in makeplot:
        planviewkml(cam, xKM, zKM, P, 5289)
    if "ray3" in makeplot:
        planview3(cam, xKM, zKM, P, 6289)
    if "sitemap" in makeplot:
        from sitemap import fancymap

        fancymap(cam)
    #%%
    if "ell" in makeplot:
        plotEachRay = False
        from EllLineLength import plotEll

        xzplot = None
        xFOVpixelEnds = empty((nCutPix, sim.nCamUsed), dtype=float)
        zFOVpixelEnds = empty_like(xFOVpixelEnds)
        xCam = empty(sim.nCamUsed, dtype=float)
        zCam = empty_like(xCam)
        for i, C in enumerate(cam):
            if C.usecam:
                xFOVpixelEnds[:, i] = C.xFOVpixelEnds
                zFOVpixelEnds[:, i] = C.zFOVpixelEnds
                xCam[i] = C.x_km
                zCam[i] = C.alt_m / 1000.0
        # we kept plotEll in EllLineLength.py for plotEachRay case :(
        plotEll(
            sim.nCamUsed,
            xFOVpixelEnds,
            zFOVpixelEnds,
            xCam,
            zCam,
            nCutPix,
            xp,
            zp,
            sz,
            sx,
            xzplot,
            sim.FwdLfn,
            plotEachRay,
            makeplot,
            P["vlim"]["p"],
        )
    #%% Picard plots
    if "picardL" in makeplot:
        plotPicard(Lfwd, drn, "L")
    if "picardLT" in makeplot:
        LxColInd = s_[Jxi * sz : (Jxi + 1) * sz]  # faster than fancy indexing
        Lx = Lfwd[:, LxColInd]  # ellipses here doesn't work
        #        LT = Lx @ Tm
        LT = Lx.dot(Tm)
        plotPicard(LT, drn, "LT")
    #%% 1-D slice plots
    if "bartrecon" in makeplot:
        plotBcompare(sim, drn, dhat["artrecon"], cam, sim.nCamUsed, "bART", tInd, P)
    #%% error plots
    if "berror" in makeplot:
        plotB(drn - dhat["art"], cam, T, P, "$\Delta{b}$")
    #%% characteristic energy determination for title labels
    #    gx0,gE0 = getx0E0(Phi0,None,fitp['EK'],xKM,tInd,odir,makeplot)
    #    if longtitle:
    #        fwdloctxt = ('\n$x_{{cam}}=${} $(x_0,E_0)=({:0.2f},{:0.0f})$ [km,eV]'.format(sim.allCamXkm,x0,E0))
    #    else:
    #        fwdloctxt=''

    bcomptxt = "best"
    #'($x_0$,$E_0$)=(' +'{:0.2f}'.format(x0) + ',' + '{:0.0f}'.format(E0) + ') [km,eV]')
    #%% Forward model plots
    if not sim.realdata and ("fwd" in makeplot or "optim" in makeplot):
        plotnoise(cam, T, P, "bnoise")

    if "fwd" in makeplot:
        plotfwd(sim, cam, drn, xKM, xp, zKM, zp, ver, Phi0, Phifit, tInd, P)
    #%% gaussian fit of optim
    if "gaussian" in makeplot and "fwd" in makeplot:
        plotBcompare(sim, drn, dhat["gaussian"], cam, sim.nCamUsed, "bgaussfit", tInd, P)

        gx0, gE0 = getx0E0(None, Phifit["gaussian"], Phifit["EK"], xKM, tInd, P, sim.minenergy)
        #'Neval = {:d}'.format(fitp.nfev)
        plotJ(
            sim,
            Phifit["gaussian"],
            xKM,
            xp,
            Phifit["EK"],
            Phifit["EKpcolor"],
            T,
            P,
            "jgaussian",
            "$\hat{\phi}_{gaussian,optim}$ diff. number flux",
        )

        logging.info(
            "Estimated $x_{{gauss,0}},E_{{gauss,0}}$={:0.2f}, {:0.0f}".format(gx0[:, 1], gE0[:, 1])
        )

        plotVER(
            sim,
            vfit["gaussian"],
            xKM,
            xp,
            zKM,
            zp,
            T,
            P,
            "vgaussian",
            "$\hat{P}_{gaussian,optim}$ volume emission rate",
            1810,
        )
    #%% optimize search plots
    if "optim" in makeplot:
        plotoptim(
            sim, cam, drn, dhat, bcomptxt, ver, Phi0, vfit, Phifit, xKM, xp, zKM, zp, tInd, P
        )
    #%% maximum entropy
    if "phimaxent" in makeplot:
        plotJ(
            sim,
            Phifit["maxent"],
            xKM,
            xp,
            Phifit["EK"],
            Phifit["EKpcolor"],
            T,
            P,
            "jme",
            "$\Phi_{maxent}$ diff. number flux",
        )

    if "phimaxent1d" in makeplot and Jxi is not None:
        xlbl = ["{:0.2f}".format(x) for x in xKM[Jxi]]
        plotJ1D(
            sim,
            Phifit["maxent"][:, Jxi],
            Phifit["EK"],
            xlbl,
            T,
            P,
            "jme_1D",
            "Differential Number flux at $B_\perp$={} [km]".format(xlbl),
        )
    if "bmaxent" in makeplot:
        plotBcompare(sim, drn, dhat["fit_maxent"], cam, sim.nCamUsed, "bmaxent", tInd, P)
    if "pmaxent" in makeplot:
        plotVER(
            sim,
            vfit["maxent"],
            xKM,
            xp,
            zKM,
            zp,
            T,
            P,
            "maxent",
            "$\hat{v}_{maxent}$ from maximum entropy regularization",
            1811,
        )
    if "pmaxent1d" in makeplot and Jxi is not None:
        xlbl = ["{:0.2f}".format(x) for x in xKM[Jxi]]
        plotVER1D(
            sim,
            vfit["maxent"][:, Jxi],
            zKM,
            xlbl,
            T,
            P,
            "vermaxent_1D",
            "$p_{optim,maxent}$  $B_\perp$={} [km]".format(xlbl),
        )
        if "pfwd1d" in makeplot:
            try:
                cax = figure().gca()
                cax.plot(vfit["maxent"][:, Jxi], zKM, label="pmaxent", color="red")
                cax.plot(ver[:, Jxi], zKM, label="pfwd", color="blue", linestyle="--")
                cax.legend(loc="best")
                cax.set_xlabel("VER")
                cax.set_ylabel("z [km]")
                cax.set_title("VER forward model vs. VER maximum entropy reconstruction")
                cax.grid(True)
                cax.yaxis.set_major_locator(MultipleLocator(dymaj))
                cax.yaxis.set_minor_locator(MultipleLocator(dymin))
                logging.info(
                    "max diff vmaxent-vfwd=" + str((vfit["maxent"][:, Jxi] - ver[:, Jxi]).max())
                )
            except Exception as e:
                logging.warning("could not plot vfwd vmaxent comparison.  {}".format(e))
    #%% diff number flux from ART
    if "jart" in makeplot:
        plotJ(
            sim,
            Phifit["art"],
            xKM,
            xp,
            Phifit["EK"],
            Phifit["EKpcolor"],
            T,
            P,
            "jart",
            "$\hat{\Phi}_{art}$ J from Kaczmarz ART on LT and b",
        )
    if "vart" in makeplot:
        assert isnan(vfit["art"]).any() == False
        plotVER(
            sim,
            vfit["art"],
            xKM,
            xp,
            zKM,
            zp,
            T,
            P,
            "vart",
            "$\hat{P}_{art}$ from ART estimation of $J$",
            1812,
        )
    if "bart" in makeplot:
        plotBcompare(sim, drn, dhat["fit_art"], cam, sim.nCamUsed, "bart", tInd, P)


def tind2dt(cam, tind):
    # NOTE: the [:-3] is arbitrary to keep 3 digits right of the decimal.

    try:  # first run
        return datetime.utcfromtimestamp(cam[0].tKeo[tind]).isoformat()[:-3]
    except IndexError:  # loading data
        return datetime.utcfromtimestamp(cam[0].tKeo).isoformat()[:-3]
    except (
        AttributeError,
        OSError,
    ):  # simdata  #OSError thrown when nan fed into utcfromtimestamp
        return str(tind)


#%%
def plotfwd(sim, cam, drn, xKM, xp, zKM, zp, ver, Phi0, fitp, tInd, P, doSubplots=True):
    assert isinstance(P, dict)
    Jxi = indone1d(xKM, P, tInd)
    #%% number of subplot rows
    nrow = 1 if Jxi is None or "optim" in P["makeplot"] else 2
    #%% number of subplot columns
    ncol = 1 if sim.realdata else 3

    T = tind2dt(cam, tInd)

    if doSubplots:
        ttxt = T + f"\n x_cam {getcamx(cam)}"
        fg, axs = subplots(nrow, ncol, figsize=(ncol * 7.5, nrow * 7.5))
        axs = atleast_2d(axs)

        fg.suptitle(ttxt)  # FIXME here we just use the fastest camera, cam 0 apriori
        fg.subplots_adjust(top=0.9)  # FIXME http://matplotlib.org/faq/howto_faq.html
        fg.text(
            1.0, 1.0, plotstamp(sim, P), ha="right", va="top", rotation="vertical", size="small"
        )
    else:
        axs = array([(None,) * nrow, (None,) * ncol])

    plotB(drn, cam, T, P, "$B_{fwd", axs[0, 0])

    if not sim.realdata:
        # Forward model VER
        plotVER(
            sim,
            ver,
            xKM,
            xp,
            zKM,
            zp,
            T,
            P,
            "pfwd",
            "$\mathbf{P}$ volume emission rate",
            axs[0, 1],
        )

        #       print('max |diff(phifwd)| = ' + str(np.abs(np.diff(phiInit, n=1, axis=0)).max()))
        plotJ(
            sim,
            Phi0,
            xKM,
            xp,
            fitp["EK"],
            fitp["EKpcolor"],
            T,
            P,
            "phifwd",
            "$\Phi_{{top}}$ diff. number flux",
            axs[0, 2],
        )

        if not "optim" in P["makeplot"] and Jxi is not None:
            xlbl = ["{:0.2f}".format(x) for x in xKM[Jxi]]

            plotVER1D(
                sim,
                ver[:, Jxi],
                None,
                zKM,
                xlbl,
                T,
                P,
                "pfwd1d",
                "$\mathbf{{P}}$ at $B_\perp$={} [km]".format(xlbl),
                axs[1, 0],
            )

            plotJ1D(
                sim,
                Phi0[:, Jxi],
                None,
                fitp["EK"],
                xlbl,
                T,
                P,
                "phifwd1d",
                "Differential Number flux at $B_\perp$={} [km]".format(xlbl),
                axs[1, 1],
            )
    #    else: #realdata
    #        plotRealImg(sim,cam,rawdata,tInd,makeplot,odir=odir)

    if doSubplots:
        closetight(fg, axs)
        writeplots(fg, "fwd", T, P["outdir"], fmt=".svg")


def plotstamp(sim, P):
    return f'{sim.optimfitmeth} iterations: {sim.optimmaxiter,}   git: {P["gitrev"]}'


def plotoptim(
    sim,
    cam,
    drn,
    dhat,
    bcomptxt,
    ver,
    Phi0,
    vfit,
    Phifit,
    xKM,
    xp,
    zKM,
    zp,
    tInd,
    P,
    doSubplots=True,
):
    assert isinstance(P, dict)
    Jxi = indone1d(xKM, P, tInd)
    #%% always 3 columns in subplot
    nrow = 1 if Jxi is None else 2

    T = tind2dt(cam, tInd)

    if isinstance(dhat, dict):
        dhat = dhat["optim"]

    if isinstance(vfit, dict):
        vfit = vfit["optim"]

    if doSubplots:
        ttxt = T + f"\n x_cam {getcamx(cam)}"
        fg, axs = subplots(nrow, 3, figsize=(21, nrow * 7.5))
        axs = atleast_2d(axs)

        fg.suptitle(ttxt)  # FIXME here we just use the fastest camera, cam 0 apriori
        # fg.subplots_adjust(top=0.95) # FIXME http://matplotlib.org/faq/howto_faq.html
        fg.text(1.0, 1.0, plotstamp(sim, P), ha="right", va="top", rotation="vertical")
    else:
        axs = array([(None,) * 3, (None,) * 3])

    plotBcompare(sim, drn, dhat, cam, "best", tInd, P, axs[0, 0])

    plotVER(
        sim,
        vfit,
        xKM,
        xp,
        zKM,
        zp,
        T,
        P,
        "pest",
        "$\hat{\mathbf{P}}$ volume emission rate",
        axs[0, 1],
    )
    #%% flux
    jtxt = "$\hat{\mathbf{\phi}}_{top}$ diff. number flux."
    if P["verbose"]:
        jtxt += f' Neval={Phifit["nfev"]}'

    if Phifit is not None:
        plotJ(
            sim,
            Phifit["x"],
            xKM,
            xp,
            Phifit["EK"],
            Phifit["EKpcolor"],
            T,
            P,
            "phiest",
            jtxt,
            axs[0, 2],
        )

        dumph5("phiest", T, P["outdir"], gx0=Phifit["gx0"], gE0=Phifit["gE0"])

    if Jxi is not None:
        # NOTE: double bracket xKM[[Jxi]] makes iterable for singleton case
        xlbl = [f"{x:0.2f}" for x in xKM[[Jxi]]]

        if ver is not None:
            vfwd1d = ver[:, Jxi]
        else:
            vfwd1d = None
        plotVER1D(
            sim,
            vfwd1d,
            vfit[:, Jxi],
            zKM,
            xlbl,
            T,
            P,
            "pest1d",
            "$\hat{\mathbf{P}}$ volume emission rate at " + f"$B_\perp$={xlbl} [km]",
            axs[1, 0],
        )

        if Phi0 is not None:
            phifwd1d = Phi0[:, Jxi]
        else:
            phifwd1d = None

        if Phifit is not None:
            plotJ1D(
                sim,
                phifwd1d,
                Phifit["x"][:, Jxi],
                Phifit["EK"],
                xlbl,
                T,
                P,
                "phiest1d",
                "$\hat{\phi}_{top}$ diff. number flux at " + "$B_\perp$={} [km]".format(xlbl),
                axs[1, 1],
            )

    # http://stackoverflow.com/questions/10035446/how-can-i-make-a-blank-subplot-in-matplotlib
    # http://stackoverflow.com/questions/2176424/hiding-axis-text-in-matplotlib-plots

    if doSubplots:
        closetight(fg, axs)
        writeplots(fg, "est", T, P["outdir"], fmt=".svg")


def closetight(fg, axs):
    """
    detect which axes have children unused
    """
    try:
        # axs[1,2].axis('off') # a bit case dependent
        for a in axs.ravel():
            if len(a.get_children()) == 10:  # FIXME is this always true?
                a.axis("off")
    except IndexError:
        pass
    fg.tight_layout(rect=(0, 0, 1, 0.95))


def getcamx(cam):
    """
    convenience function
    returns all camera x position in km as list of formatted string
    """
    return [f"{c.x_km:.2f}" for c in cam if c.usecam]


#%%
def plotnoise(cam, T, P, prefix):
    assert isinstance(P, dict)
    fg, axs = subplots(2, 1, sharex=True)

    ax = axs[0]
    for C in cam:
        if C.usecam:
            if not hasattr(C, "dnoise"):  # noiseless sim
                return

            ax.plot(C.dnoise, label=C.name)
            ax.set_ylabel("amplitude")
            ax.set_title("Noise that was injected into raw intensity data")
            ax.grid(True)
    ax.legend(loc="best")

    ax = axs[1]
    for C in cam:
        if C.usecam:
            ax.plot(C.noisy, label=C.name)
            ax.set_ylabel("amplitude")
            ax.set_xlabel("pixel number")
            ax.set_title("Noisy data")
            ax.grid(True)
    ax.legend(loc="best")
    ax.autoscale(True, "x", True)

    writeplots(fg, prefix, T, P["outdir"])


def plottphi0(Tm, Phi0, Jxi, Ek, zKM, vlim, sim, T, P, prefix):
    assert isinstance(P, dict)

    fg = figure()
    ax = fg.gca()

    for i, e in enumerate(Ek):
        # try:
        ax.plot(Tm[:, i] * Phi0[i, Jxi], zKM, label="{:0.0f}".format(e) + "eV")
    # except ValueError:
    #    print('skipped plotting {:0.0f} eV due to zero diff. num flux at that energy'.format(e))
    ax.set_xscale("log")
    ax.set_title("individual eigenprofile contributions to $P_{fwd}$")
    ax.set_xlabel("volume emission rate [photons cm$^{-3}$ s$^{-1}$]")
    ax.set_ylabel("$B_\parallel$ [km]")
    ax.grid(True)

    ax.legend(loc="upper left", framealpha=0.5)

    ax.yaxis.set_major_locator(MultipleLocator(dymaj))
    ax.yaxis.set_minor_locator(MultipleLocator(dymin))
    ax.tick_params(axis="both", which="both", direction="in")
    ax.set_xlim(vlim[4:])
    ax.set_ylim(vlim[2:-2])

    writeplots(fg, prefix, T, P["outdir"])


def ploteig1d(Ek, zKM, Tm, vlim, sim, T, P, prefix=None):
    assert isinstance(P, dict)

    firstbeamind = 0

    beamsel = s_[firstbeamind : -firstbeamind - 1]
    fg = figure()
    ax = fg.gca()

    for i, e in enumerate(Ek[beamsel], firstbeamind):
        ax.semilogx(Tm[:, i], zKM, label="{:0.0f}".format(e) + "eV")  # ,marker='.')
    ax.yaxis.set_major_locator(MultipleLocator(dymaj))
    ax.yaxis.set_minor_locator(MultipleLocator(dymin))
    ax.set_ylabel("$B_\parallel$ [km]")
    ax.set_xlabel("volume emission rate [photons cm$^{-3}$s$^{-1}$]")
    ax.tick_params(axis="both", which="both", direction="in")
    ax.set_xlim(vlim[4:])
    ax.set_ylim(vlim[2:4])
    titletxt = "$P_{eig}$ "
    titletxt += str(sim.reacreq)

    titletxt += " Opt. Filter: " + sim.opticalfilter
    ax.set_title(titletxt)
    ax.legend(loc="upper left", framealpha=0.5)
    # ax.autoscale(True,tight=True)
    ax.grid(True)
    writeplots(fg, prefix, T, P["outdir"])


def plotPicard(A, b, cvar=None):
    from pyAIRtools.picard import picard
    from scipy.sparse import issparse
    from numpy.linalg import svd

    logging.info("computing SVD for Picard plot: {}  ...".format(cvar))
    if issparse(A):
        [U, s, V] = svd(A.todense(order="F"), full_matrices=False, compute_uv=1)  # V is not used!
    else:
        [U, s, V] = svd(A, full_matrices=False, compute_uv=1)  # V is not used!
    picard(asfortranarray(U), s, b)


def plotJ1D(sim, PhiFwd, PhiInv, Ek, xlbl, T, P, prefix, titletxt, ax=None):
    assert isinstance(P, dict)

    fg, ax = fighandler(ax)

    lfwd = "$\Phi|x=$"
    linv = "$\hat{\Phi}|x=$"

    for Phi, l in zip((PhiFwd, PhiInv), (lfwd, linv)):
        if Phi is not None:
            assert Phi.ndim in (1, 2)
            Phi[Phi == 0] = 1e-30  # to avoid log(0)

            try:
                if Phi.ndim == 1:
                    ax.loglog(Ek, Phi, marker=".", label=l + str(xlbl[0]))  # xlbl[0], not .item()
                    if P["verbose"]:
                        labelpeakE(Phi, Ek, sim.minenergy, ax)
                else:
                    assert Phi.shape[1] == len(xlbl)
                    for i in range(Phi.shape[1]):
                        ax.loglog(Ek, Phi[:, i], marker=".", label=l + str(xlbl[i]))

                        if P["verbose"]:
                            labelpeakE(Phi[:, i], Ek, sim.minenergy, ax)

            except ValueError as e:
                logging.error(
                    "could not plot Jfwd1D due to non-positive value(s) in Jflux, t= {}   {}"
                    "\n did you pick the correct --x1d ?   {}".format(T, titletxt, e)
                )

    ax.grid(True, "both")
    ax.autoscale(True, tight=False)
    ax.set_ylim(P["vlim"]["j1d"])
    ax.set_xlim([Ek[0] * 0.98, Ek[-1] * 1.05])

    ax.set_xlabel("particle energy [eV]")
    ax.set_ylabel("Differential Number Flux  [cm$^{-2}$s$^{-1}$eV$^{-1}$]")
    ax.set_title(titletxt)
    ax.legend(loc="upper right")

    ax.tick_params(axis="both", which="both")

    if P["verbose"]:
        ax.legend(loc="lower left")

    writeplots(fg, prefix, T, P["outdir"])

    dumph5(prefix, T, P["outdir"], PhiFwd1d=PhiFwd, PhiInv1d=PhiInv, Ek=Ek)


#%%
def labelpeakE(Phi, Ek, E0min, ax):
    assert Phi.ndim == 1

    Phitmp = Phi.copy()
    Phitmp[Ek < E0min] = 0
    iE0est = Phitmp.argmax()
    E0est = Ek[iE0est]

    ax.axvline(E0est, linestyle="--", color="red")
    ax.annotate(
        ("$\hatE_0$={:0.0f}".format(E0est) + " eV"),
        xy=(E0est, Phi[iE0est]),
        xytext=(E0est * 0.75, Phi[iE0est] * 0.2),
        ha="right",
        va="top",
        arrowprops={"facecolor": "red", "shrink": 0.2, "headwidth": 8, "width": 2},
    )


#%%
def plotJ(sim, Jflux, x, xp, Ek, EKpcolor, T, P, prefix, titletxt, ax=None):
    assert isinstance(P, dict)

    cnorm, sfmt = logfmt(P)
    plt3 = "octave"  #'octave' #'mpl'#'mayavi'
    #%% 2-D
    pre = ("lin", "log")
    vlow = (spacing(1), 1.0)
    for c, s, v, p in zip(cnorm, sfmt, vlow, pre):
        # determine lowest level to plot
        vmin = getmin(v, P["vlim"]["j"][0])
        # print('using phi plot limits ({:.1e},  {:.1e})'.format(vmin,vlim[1]))
        vmax = P["vlim"]["j"][1] if P["vlim"]["j"] is not None else Jflux.max()

        if "plotly" in P["makeplot"]:
            dpy = Data(
                [Contour(x=x, y=Ek, z=Jflux, xaxis="$B_\perp$ [km]", yaxis="$B_\parallel$ [km]")]
            )
            dlay = Layout(xaxis=XAxis(range=[vmin, vmax]), yaxis=YAxis(range=P["vlim"]["j"]))

            dfg = Figure(data=dpy, layout=dlay)

            py.plot(dfg, filename="{}_{}_{}".format(P["outdir"], prefix, T), auto_open=False)
        else:

            fg, ax = fighandler(ax)

            if pstyle == "pcolor":
                hc = ax.pcolormesh(
                    xp,
                    EKpcolor,
                    Jflux,
                    edgecolors="none",
                    norm=c,
                    rasterized=False,  # cmap=pcmcmap,
                    vmin=vmin,
                    vmax=vmax,
                )  # vmin can't be 0 when using LogNorm!
                # my recollection is that rasterized=True didn't really help savefig speed
            elif pstyle == "contour":
                if vmin and vmax:
                    clvl = logspace(log10(vmin), log10(vmax), 6)
                else:
                    clvl = None

                logging.debug("plotting flux Phi using contour levels {}".format(clvl))

                hc = ax.contour(
                    x, Ek, Jflux, levels=clvl, linewidths=2, norm=c, vmin=v, vmax=vmax,
                )
            """
            remember colorbar ticks set themselves automatically to the data for
            contours. vmin/vmax sets the color extremes, but not the colorbar ticks.
            colorbar ticks are set inside colorbar with colorbar(...,ticks=[...])
            http://stackoverflow.com/questions/16695275/set-limits-on-a-matplotlib-colorbar-without-changing-the-actual-plot
            """
            cbar = colorbar(hc, ax=ax, format=s)
            cbar.set_label("[cm$^{-2}$s$^{-1}$eV$^{-1}$]")
            # now let's fix the exponent label on the colorbar
            #           cbar.ax.yaxis.get_offset_text().set_size(afs)
            cbar.ax.yaxis.get_offset_text().set_position((2, 10))
            if pstyle == "contour":
                cbar.add_lines(hc)

            ax.set_yscale("log")
            # print('phi xlim {}'.format(xlim))
            ax.set_xlim(P["vlim"]["x"])

            ax.grid(True, which="both")

            _doJlbl(fg, ax, titletxt)

            writeplots(fg, prefix + p, T, P["outdir"])

    #%% 3-D
    if "3d" in P["makeplot"]:
        try:
            ax3 = plotJ3(x, EKpcolor, Jflux, plt3)
        except Exception as e:
            logging.info("could not do 3-D, falling back to matplotlib.  {}".format(e))
            ax3 = plotJ3(x, EKpcolor, Jflux, "mpl")
        _doJlbl(ax3, titletxt)

    dumph5(prefix, T, P["outdir"], phi=Jflux, xp=xp, Ek=Ek, EKpcolor=EKpcolor)


def _doJlbl(fg, ax, titletxt):

    if not fg:
        fg = ax.figure

    fg.subplots_adjust(top=0.85)

    ax.set_ylabel("Energy [eV]")
    ax.set_xlabel("$B_\perp$ [km]")
    ax.set_title(titletxt)

    ax.xaxis.set_major_locator(MultipleLocator(dxmax))
    ax.xaxis.set_minor_locator(MultipleLocator(dxmin))

    ax.tick_params(axis="both", which="both", direction="out")


#%%
def plotJ3(x, EKpcolor, Jflux, plt3):
    if plt3 == "mpl":
        x, e = meshgrid(x, EKpcolor)
        ax3 = figure().gca(projection="3d")
        ax3.plot_wireframe(x, e, Jflux)
        # ax3.yaxis.set_scale('log')
    elif plt3 == "mayavi":
        ax3 = None
        from mayavi import mlab

        mlab.figure()
        # this .axes command not working
        # axm = mlab.axes(xlabel='x [km]',ylabel='Beam Energy [eV]',x_axis_visibility=True, y_axis_visibility=True)

        # mobj = mlab.mesh(e,x,Jflux, representation='wireframe')
        # mobj.actor.actor.scale = [1,0.0001,1]
        # http://docs.enthought.com/mayavi/mayavi/auto/mlab_helper_functions.html#mayavi.mlab.mesh
        # surf is preferred over mesh in this case

        mlab.surf(x, EKpcolor, Jflux, warp_scale="auto", representation="wireframe")
    elif plt3 == "octave":
        from oct2py import octave

        ax3 = None
        x, e = meshgrid(x, EKpcolor)
        octave.Jmesh(x, e, Jflux)
    return ax3


def getmin(vs, vu):
    if vu is not None:
        return max(vs, vu)
    else:
        return vs


def plotVER1D(sim, pfwd, pinv, zKM, xlbl, T, P, prefix="", titletxt="", ax=None):
    assert isinstance(P, dict)

    fg, ax = fighandler(ax)

    lfwd = "$\mathbf{P}|x=$"
    linv = "$\hat{\mathbf{P}}|x=$"

    for p, l in zip((pfwd, pinv), (lfwd, linv)):
        if p is not None:
            assert p.ndim in (1, 2)

            try:
                p[p == 0] = 1e-30  # to avoid log(0)
                """
                list comprehension goofed up escapes, what a mess.
                """
                if p.ndim == 1:
                    ax.semilogx(p, zKM, label=l + str(xlbl[0]))  # xlbl[0], not .item()
                else:
                    assert p.shape[1] == len(xlbl)
                    for i in range(p.shape[1]):
                        ax.semilogx(p[:, i], zKM, label=l + str(xlbl[i]))

            except ValueError as e:
                logging.warning("{} in 1D VER plot. maybe negative value snuck in.".format(e))

    ax.legend(loc="upper right")
    ax.set_xlabel("Volume emission rate [photons cm$^{-3}$s$^{-1}$]")
    ax.set_ylabel("$B_\parallel$ [km]")

    #    if not sim.loadver:
    #        titletxt += '\nReactions: {}'.format(sim.reacreq)

    ax.set_title(titletxt)

    ax.yaxis.set_major_locator(MultipleLocator(dymaj))
    ax.yaxis.set_minor_locator(MultipleLocator(dymin))
    ax.tick_params(axis="both", which="major", direction="in")
    ax.grid(True, "both")

    ax.set_ylim(P["vlim"]["z"])
    ax.set_xlim(P["vlim"]["p1d"])

    writeplots(fg, prefix, T, P["outdir"])

    dumph5(prefix, T, P["outdir"], pfwd1d=pfwd, pinv1d=pinv, z=zKM)


#%%
def plotVER(sim, ver, x, xp, z, zp, T, P, prefix="", titletxt="", ax=None):
    assert isinstance(P, dict)

    cnorm, sfmt = logfmt(P)
    """
    # http://stackoverflow.com/questions/13943217/how-to-add-colorbars-to-scatterplots-created-like-this
    # http://stackoverflow.com/questions/18856069/how-to-shrink-a-subplot-colorbar
    """
    vlow = (spacing(1), 1.0)
    pre = ("lin", "log")

    if ver is not None:
        for c, s, v, p in zip(cnorm, sfmt, vlow, pre):
            # determine lowest level to plot
            vmin = getmin(v, P["vlim"]["p"][0])
            vmax = P["vlim"]["p"][1] if P["vlim"]["p"][1] is not None else ver.max()

            if "plotly" in P["makeplot"]:
                dpy = Data([Contour(x=x, y=z, z=ver)])
                dlay = Layout(
                    xaxis=XAxis(range=[vmin, vmax], title="$B_\perp$ [km]"),
                    yaxis=YAxis(range=P["vlim"]["p"], title="$B_\parallel$ [km]"),
                )

                dfg = Figure(data=dpy, layout=dlay)

                py.plot(dfg, filename="{}_{}_{}".format(P["outdir"], prefix, T), auto_open=False)
            else:
                fg, ax = fighandler(ax)

                if pstyle == "pcolor":
                    hc = ax.pcolormesh(
                        xp,
                        zp,
                        ver,
                        edgecolors="none",
                        norm=c,  # cmap=pcmcmap,n
                        vmin=vmin,
                        vmax=vmax,
                        rasterized=True,
                    )
                    ax.autoscale(True, tight=True)  # need this to fill axes (does not resize axes)

                elif pstyle == "contour":
                    clvl = logspace(log10(vmin), log10(vmax), 6)

                    hc = ax.contour(
                        x, z, ver, levels=clvl, linewidths=2, norm=c, vmin=vmin, vmax=vmax,
                    )
                    # ax.clabel(hc,fontsize=6,inline=True)
                    # hc.ax.get_children().set_linewidths(5.0)
                """
            remember colorbar ticks set themselves automatically to the data for
            contours. vmin/vmax sets the color extremes, but not the colorbar ticks.
            colorbar ticks are set inside colorbar with colorbar(...,ticks=[...])
            http://stackoverflow.com/questions/16695275/set-limits-on-a-matplotlib-colorbar-without-changing-the-actual-plot
            """
                cbar = colorbar(hc, ax=ax, format=s)
                cbar.set_label("[photons cm$^{-3}$s$^{-1}$]")
                #            cbar.ax.yaxis.get_offset_text().set_size(afs)
                cbar.ax.yaxis.get_offset_text().set_position((2, 10))
                if pstyle == "contour":
                    cbar.add_lines(hc)

                ax.yaxis.set_major_locator(MultipleLocator(dymaj))
                ax.yaxis.set_minor_locator(MultipleLocator(dymin))
                ax.xaxis.set_major_locator(MultipleLocator(dxmax))
                ax.xaxis.set_minor_locator(MultipleLocator(dxmin))
                ax.tick_params(axis="both", which="both", direction="out")
                ax.grid(True, "both")  # need both for seaborn

                ax.set_xlabel("$B_\perp$ [km]")
                ax.set_ylabel("$B_\parallel$ [km]")

                ax.set_xlim(P["vlim"]["x"])
                # print(P['vlim']['z'])
                ax.set_ylim(P["vlim"]["z"])
                ax.set_title(titletxt)

                writeplots(fg, prefix + p, T, P["outdir"])
    else:
        text(0, 0, "Using Actual Data (ver=None)")

    dumph5(prefix, T, P["outdir"], p=ver, x=x, xp=xp, z=z, zp=zp)


#%%
def plotBcompare(sim, braw, bfit, cam, prefix, tInd, P, ax=None):
    assert isinstance(P, dict)
    T = tind2dt(cam, tInd)

    dosubtract = False

    fg, ax = fighandler(ax)
    #%% plot raw
    cnorm, sfmt = logfmt(P, (-3, 3))
    ax.get_yaxis().set_major_formatter(sfmt[0])  # only need lin

    #    ax1.yaxis.get_offset_text().set_size(afs)
    ax.tick_params(axis="both", which="both", direction="out")
    ax.set_ylabel("$\mathbf{B}$ [photons sr$^{-1}$ s$^{-1}$]")

    for C in cam:
        if C.usecam:
            # find pixels that were used from this camera
            ax.plot(
                C.angle_deg[C.Lcind], braw[C.Lind], label=("$\mathbf{{B}}_{}$".format(C.name)),
            )
            # color=cord[icm])#)
    #%% plot fit
    # do we need twinax? Let's find out if they're within factor of 10
    singax = True
    if bfit is not None:
        maxfit = bfit.max()
        maxraw = braw.max()
        if 10 * maxraw > maxfit > 0.1 * maxraw:
            ax2 = ax
        else:
            singax = False
            ax2 = ax.twinx()
            ax2.get_yaxis().set_major_formatter(sfmt[0])  # only need lin
            ax2.set_ylabel("$\mathbf{\hat{B}}$ [photons sr$^{-1}$ s$^{-1}$]")

        #%% now plot each camera
        for C in cam:
            if C.usecam:
                ax2.plot(
                    C.angle_deg[C.Lcind],
                    bfit[C.Lind],
                    label="$\hat{{\mathbf{{B}}}}_{}$".format(C.name),
                )
                # color=cord[icm]))

    if singax:
        ax.legend(loc="lower left")
    else:
        """
        legend for twinx http://stackoverflow.com/questions/5484922/secondary-axis-with-twinx-how-to-add-to-legend
        """
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper right")

    ax.set_title("$\mathbf{B}$ ground-observed intensity")

    ax.set_xlabel("local view angle [deg.]")
    ax.xaxis.set_major_locator(MultipleLocator(1))

    ax.grid(True)
    ax.autoscale(True, axis="x", tight=True)
    ax.set_ylim(P["vlim"]["b"])  # after autoscale
    #%% do more detailed comparison
    if dosubtract and bfit is not None:
        bias = []
        ax3 = figure().gca()
        for C in cam:
            if C.usecam:
                bias.append(bfit[C.Lind].max() - braw[C.Lind].max())
                ax3.plot(C.angle_deg[C.Lcind], braw[C.Lind] - (bfit[C.Lind]))  # -bias[iCam]))

        ax3.set_title("error $\mathbf{{B}}_{{fwd}} - B_{{est}}, bias={}".format(bias))
        #  $t_i=' + str(tInd) + '$'
        ax3.set_xlabel("local view angle [deg.]")
        ax3.xaxis.set_major_locator(MultipleLocator(1))
        ax3.set_ylabel("error")
        ax3.get_yaxis().set_major_formatter(sfmt[0])

    if sim.realdata:
        try:
            ut1_unix = [c.tKeo[tInd] for c in cam if c.usecam]
        except IndexError:
            ut1_unix = [c.tKeo for c in cam if c.usecam]
    else:
        ut1_unix = nans(len(cam))

    dumph5(
        prefix,
        T,
        P["outdir"],
        angle=[C.angle_deg for C in cam if C.usecam],
        braw=braw,
        bfit=bfit,
        ut1_unix=ut1_unix,
    )

    writeplots(fg, prefix, T, P["outdir"], fmt=".eps")


#%%
def plotB(bpix, cam, T, P, labeltxt="", ax=None):
    assert isinstance(P, dict)

    cnorm, sfmt = logfmt(P)

    fg, ax = fighandler(ax)

    std = []
    #%% do we need twinax? Let's find out if they're within factor of 10
    #    thiscammax = empty(len(cam))
    #    for c in cam:
    #      if c.usecam:
    #        thiscammax[c] = bpix[cam[c].ind].max()
    #    maxraw = thiscammax.max(); minmaxraw = thiscammax.min()
    #    if 10*maxraw > minmaxraw > 0.1*maxraw:
    #        singax = True
    #        ax2 = ax
    #        ax.set_ylabel('$b$ Data Numbers')
    #    else:
    #        singax = False
    #        ax2 = ax.twinx()
    #        ax2.get_yaxis().set_major_formatter(sfmt)
    #        ax.set_ylabel('$b_{raw}$ data numbers')
    #        ax2.set_ylabel( fittxt + ' Data Numbers')
    #%% make plot
    for C in cam:
        if C.usecam:
            if C.noiselam is not None:
                std.append("{:0.1e}".format(C.noiselam))

            ax.plot(C.angle_deg[C.Lcind], bpix[C.Lind], label=labeltxt + "," + str(C.name) + "}$")
            # marker='.',
            # color=cord[c])
    doBlbl(ax, sfmt[0], P["vlim"]["b"], labeltxt, std)  # b is never log

    writeplots(fg, "b" + labeltxt[4:7], T, P["outdir"])


def doBlbl(axb, sfmt, vlim, labeltxt, noiselam):
    axb.legend(loc="upper left")
    axb.set_title("Observer Intensity")

    #    if not isrealdata and noiseStd:
    #        ax.text(0.05,0.95,'noise std. dev.=' +noiseStd,
    #                transform=ax.transAxes,va='top',ha='left')
    axb.set_xlabel("local view angle [deg.]")

    axb.xaxis.set_major_locator(MultipleLocator(dxmax))
    axb.xaxis.set_minor_locator(MultipleLocator(dxmin))
    axb.tick_params(axis="both", which="both", direction="out")

    # sfmt.set_powerlimits((-6, 6))
    axb.yaxis.set_major_formatter(sfmt)

    axb.set_ylabel(labeltxt + "}$ [photons sr$^{-1}$ s$^{-1}$]")  # yes the }$ is appropriate

    axb.grid(True, which="major")
    axb.autoscale(True, tight=True)
    axb.set_ylim(vlim)  # must come AFTER autoscale!


def allLinePlot(simfilelist):
    #%% priming
    nsim = len(simfilelist)
    nt = len(simfilelist[0])
    with h5py.File(str(simfilelist[0][0]), "r", libver="latest") as fid:
        J0 = fid["/Jn/j0"].value
        nE = J0.shape[0]
        Ek = fid["/EK"].value

    Jme = empty((nsim, nE, nt), dtype=float, order="F")
    #%% working
    for ti in range(nt):
        for si, fnlist in enumerate(simfilelist):
            with h5py.File(str(fnlist[ti]), "r", libver="latest") as fid:
                Jme[si, :, ti] = fid["/Jn/jme_1D"].value

        ax = figure(ti).gca()
        ax.plot(Ek, Jme[:, :, ti])


#%%
def planview3(cam, xKM, zKM, P):
    assert isinstance(P, dict)
    from pymap3d import aer2ecef, geodetic2ecef

    fg = figure()  # ; fg.clf()
    ax = fg.gca(projection="3d")
    az = 106.444916022  # TODO arbitrary should be from real camera pointing
    srange = 500e3  # [m]
    decimaterayfactor = 16
    clr = ["r", "b", "g", "m"]

    for C in cam:
        if C.usecam:
            el = C.angle_deg[::decimaterayfactor]  # yes double colon
            Np = el.size
            x0, y0, z0 = geodetic2ecef(C.lat, C.lon, C.alt_m)
            # get LLA of pixel rays at 100km altitude
            xray, yray, zray = aer2ecef(az, el, srange, C.lat, C.lon, C.alt_m)
            # camera rays
            for cri in range(Np):
                ax.plot((x0, xray[cri]), (y0, yray[cri]), (z0, zray[cri]), color=clr[C.name])

    # plot sphere
    earthrad = 6371e3  # [m]
    Nps = 50
    u = linspace(0, 2 * pi, Nps)
    v = linspace(0, pi, Nps)

    x = earthrad * outer(cos(u), sin(v))
    y = earthrad * outer(sin(u), sin(v))
    z = earthrad * outer(ones_like(u), cos(v))
    ax.plot_surface(x, y, z, rstride=4, cstride=4, color="g")


#%% gaussian fit
def getx0E0(Phifwd, Phifit, E, x, tInd, P, E0min):
    assert isinstance(P, dict), "function arguments: out of order?"

    Npts = 200
    Nptsfits = (Npts // 40, Npts // 20)  # (nEnergyToUse+-, nXtouse+-)

    def clipPhi(fwd, fit, E):
        Elin = linspace(E[0], E[-1], Npts)

        try:
            phifwd = fwd.copy()
            phifwd[E < E0min, :] = 0.0
            f = interp1d(E, phifwd, kind="linear", axis=0)
            fwdlin = f(Elin)
        except AttributeError:
            fwdlin = None

        try:
            phifit = fit.copy()
            phifit[E < E0min, :] = 0.0
            f = interp1d(E, phifit, kind="linear", axis=0)
            fitlin = f(Elin)
        except AttributeError:
            fitlin = None

        return fwdlin, fitlin, Elin

    cPhifwd, cPhifit, Elin = clipPhi(Phifwd, Phifit, E)
    #%% first guess of 2-D peak, take region of pixels near the peak to fit
    # note that unravel_index for jf must be order='C'
    def gfitphi(Philin, Elin):
        if Philin is None:
            return nan, nan, None, None

        pkrow, pkcol = unravel_index(Philin.argmax(axis=None), Philin.shape, order="C")
        nh = Nptsfits  # MxN region to extract
        rcpluck = pkrow - nh[0], pkcol - nh[1]
        gpeak = Philin[rcpluck[0] : pkrow + nh[0], rcpluck[1] : pkcol + nh[1]]
        # set_trace()
        try:
            gparam = gaussfit(gpeak, returnfitimage=False)
        except ValueError:
            logging.error(
                "gaussian fit peak against edge of model space."
                "gpix shape {} row {} col {}".format(gpeak.shape, pkrow, pkcol)
            )
            return nan, nan, None, None

        Ghcol = int(round(gparam[2] + rcpluck[1]))
        Ghrow = int(round(gparam[3] + rcpluck[0])) + 1  # altitude of peak

        gparamshift = gparam.copy()
        gparamshift[2] = gparam[2] + rcpluck[1]
        gparamshift[3] = gparam[3] + rcpluck[0]
        gpix = twodgaussian(gparamshift, shape=Philin.shape)

        try:
            return x[Ghcol], Elin[Ghrow], gpix, gpeak
        except IndexError:
            logging.error("gaussian fit was outside model space")
            return nan, nan, None, None

    gx0 = empty(2)
    gE0 = empty(2)
    gpix = []
    gpeak = []
    for i, p in enumerate((cPhifwd, cPhifit)):
        gx0[i], gE0[i], gp, gk = gfitphi(p, Elin)
        gpix.append(gp)
        gpeak.append(gk)

    if "gfit" in P["makeplot"]:
        fg, ax = subplots(2, 3, sharey=False, sharex=False)

        ca = ax[0, 0]
        try:
            hb = ca.pcolormesh(x, Elin, cPhifwd)
            fg.colorbar(hb, ax=ca)
            ca.set_title("$\Phi$ fwd precip. intensity")
            # ca.set_xlabel('$B_\perp$ [km]')
            ca.set_ylabel("Beam Energy [eV]")
            ca.set_yscale("log")
            ca.autoscale(True, tight=True)
        except AttributeError:
            ca.text(0, 0, "$\Phi$ Not Used")

        ca = ax[0, 1]
        try:
            hp = ca.pcolormesh(gpeak[0])
            fg.colorbar(hp, ax=ca)
            ca.set_title(
                "$\Phi$ peak region to fit:"
                " $B_{{\perp,0}},E_0$={:.2f},{:.0f})".format(gx0[0], gE0[0])
            )
            # ca.set_yscale('log')
            ca.autoscale(True, tight=True)  # ValueError: cannot convert float NaN to integer
        except AttributeError:
            ca.text(0, 0, "$\Phi$ not used")

        ca = ax[0, 2]
        try:
            hp = ca.pcolormesh(x, Elin, gpix[0])
            fg.colorbar(hp, ax=ca)
            ca.set_title(
                "$\Phi$ gaussian fit:" " $B_{{\perp,0}},E_0$={:.2f},{:.0f})".format(gx0[0], gE0[0])
            )
            ca.set_yscale("log")
            ca.autoscale(True, tight=True)
        except AttributeError:
            ca.text(0, 0, "$\Phi$ not used")

        ca = ax[1, 0]
        try:
            hb = ca.pcolormesh(x, Elin, cPhifit)
            fg.colorbar(hb, ax=ca)
            ca.set_title("$\hat{\Phi}$ est. precip. intensity")
            ca.set_xlabel("$B_\perp$ [km]")
            ca.set_ylabel("Beam Energy [eV]")
            ca.set_yscale("log")
            ca.autoscale(True, tight=True)
        except AttributeError:
            ca.text(0, 0, "$\hat{\Phi} not used")

        ca = ax[1, 1]
        try:
            hp = ca.pcolormesh(gpeak[1])
            fg.colorbar(hp, ax=ca)
            ca.set_title(
                "$\hat{{\Phi}}$ peak region to fit:"
                " $B_{{\perp,0}},E_0$={:.2f},{:.0f})".format(gx0[1], gE0[1])
            )
            # ca.set_yscale('log')
            ca.autoscale(True, tight=True)
        except AttributeError:
            ca.text(0, 0, "$\hat{\Phi}$ not used")

        ca = ax[1, 2]
        try:
            hp = ca.pcolormesh(x, Elin, gpix[1])
            fg.colorbar(hp, ax=ca)
            ca.set_title(
                "$\hat{{\Phi}}$ est. via gaussian fit:"
                " $\hat{{B}}_{{\perp,0}}, \hat{{E}}_0$={:.2f},{:.0f})".format(gx0[1], gE0[1])
            )
            ca.set_xlabel("$B_\perp$ [km]")
            ca.set_yscale("log")
            ca.autoscale(True, tight=True)
        except AttributeError:
            ca.text(0, 0, "$\hat{\Phi} not used")

        writeplots(fg, "gaussfitlin", tInd, P["outdir"])

    # Ghrow,Ghcol = np.unravel_index(gfit.argmax(axis=None),gfit.shape, order='C')

    return gx0, gE0  # , x[pkcol], Elin[pkrow]


#%% write hdf5
def dumph5(prefix, tInd, odir=None, **writevar):  # used in other .py too
    if prefix is None or odir is None:
        return

    fn = Path(odir).expanduser() / (f"dump {nametime(tInd)}.h5")

    if not fn.is_file():
        print(f"creating {fn}")

    logging.info(f"dumping {prefix} to {fn}")
    with h5py.File(str(fn), "a", libver="latest") as H:
        for k, v in writevar.items():
            if v is None:
                continue

            K = "/{}/{}".format(prefix, k)
            if K in H:  # allow for overwriting with different sized array
                del H[K]

            try:
                if isinstance(v, ndarray) and v.ndim > 1:
                    H.create_dataset(K, data=v, compression="gzip")
                else:
                    H[K] = v
            except Exception as e:
                logging.error(f"failed to write {fn} {K}.  {e}")


def indone1d(x, P, i):
    assert isinstance(P, dict), "function arguments: out of order?"
    #%% handle varied user input
    if "x1d" not in P or P["x1d"] is None:
        return

    if isinstance(P["x1d"], (float, int, list, tuple, ndarray)):
        c = P["x1d"]
    elif len(P["x1d"]) == 1:
        c = P["x1d"].item()
    elif isinstance(P["x1d"], dict):
        try:  # FIXME future didn't implement distinction in configparse code yet
            c = P["x1d"]["time"][i]
        except IndexError:
            logging.error(f"used last value of x1d: {c} km")
            c = P["x1d"]["time"][-1]
    else:
        logging.warning(f'unknown intent for "x1d" {P["x1d"]}')
        return
    #%%
    """
    Note: Jxi can be a scalar OR vector!
    """
    Jxi = find_nearest(x, c)[0]
    print(f'1-D plots of Phi and P taken at index {Jxi}  x={P["x1d"]} km')

    return Jxi


def fighandler(ax):
    """
    subplot: ax=Axes  <-- do nothing
    newfig:  ax=None   <--create new figure
    """
    if ax is None:  # new figure, create axes
        fg = figure()
        ax = fg.gca()
    else:
        fg = None  # disables savefig, for existing subplots

    return fg, ax
