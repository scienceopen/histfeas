#!/usr/bin/env python
"""
Figures of flaming aurora generated by HiST program

intended for use with in/{2,3}cam_flame.ini
"""
from histfeas import userinput, hist_figure

if __name__ == '__main__':
    P = userinput(ini='../in/3cam_flame.ini',outdir='out/3camflame')

    P['x1d'] = 1.
    P['vlim'] = {'p':[-1.5,4.5,90,300,5e7,8e8,5e7,2e9], 'j':[1e3,1.1e5, 1e3,8e5],
            'b':[0,1.5e3]}

    if not P['load']:
        hist_figure(P)
#%%
    from histfeas.loadAnalyze import readresults,findxlsh5
    h5list,xlsfn = findxlsh5(P['outdir'])
    readresults(h5list,P)
