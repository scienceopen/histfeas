"""
sanity check for HST simulation parameters
Michael Hirsch
"""
from pathlib import Path
import logging
from pandas import read_excel
from warnings import warn
from shutil import copy2
#
from .camclass import Cam
from .simclass import Sim


def getParams(XLSfn,overrides,makeplot,odir):
    XLSfn = Path(XLSfn).expanduser()
    if odir is not None:
        copy2(str(XLSfn),str(odir))
#%% read spreadsheet
    #paramSheets = ('Sim','Cameras','Arc')
    xl = read_excel(str(XLSfn),sheetname=None,index_col=0,header=0)
    sp = xl['Sim']
    cp = xl['Cameras']
#%% read arcs (if any)
    ap = {}; ntimeslice=None
    for s in xl:
        if s.startswith('Arc'):
            ap[s] = xl[s]
            if ntimeslice is not None and ap[s].shape[1]-1 != ntimeslice:
                raise ValueError('for now, all Arcs must have same number of times (columns)')
            ntimeslice=ap[s].shape[1]-1

    logging.info('# of observer time steps in spreadsheet: {}'.format(ntimeslice))
#%% ***** must be outside camclass ********
    nCutPix = cp.loc['nCutPix'].values
    if not (nCutPix == nCutPix[0]).all():
        raise ValueError('sanityCheck: all cameras must have same 1D cut length')
#%% class with parameters and function
    sim = Sim(sp,cp,ap,ntimeslice,overrides,makeplot,odir)
#%% grid setup
    Fwd = sim.setupFwdXZ(sp)
#%% setup cameras
    cam,cp = setupCam(sim,cp,Fwd['z'][-1])

    # make the simulation time step match that of the fastest camera
    sim.kineticsec = min([C.kineticsec for C,u in zip(cam,sim.useCamBool) if u])


    logging.info('fwd model voxels:\n'
          'B_perp: N={}   B_parallel: M={}'.format(Fwd['sx'],Fwd['sz']))
#%% init variables
    return ap,sim,cam,Fwd
###############################################

def setupCam(sim,cp,zmax):
    cam = []

    if sim.camxreq[0] is not None:
        warn('overriding camera x-loc with {}'.format(sim.camxreq))
        for i,(c,cx) in enumerate(zip(cp,sim.camxreq)):
            if sim.useCamBool[i]:
                cp.iat['Xkm',c] = cx
                cam.append(Cam(sim,cp[c], c, zmax))
    else:
        for i,c in enumerate(cp):
            if sim.useCamBool[i]:
                cam.append(Cam(sim,cp[c], c, zmax))

    if len(cam)==0:
        raise ValueError('0 cams are configured, Nothing to do.')
    return cam,cp
