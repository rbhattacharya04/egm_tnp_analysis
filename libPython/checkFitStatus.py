### python specific import

## example
# python libPython/checkFitStatus.py plots/results_test_globalMuons_byCharge_noMinos_RooMinimizerMinuit2//efficiencies_GtoH/mu_iso_plus/mu_RunGtoH_mu_iso_plus.nominalFit.root

import os
import pickle
import shutil
import copy
import argparse

## safe batch mode
import sys
args = sys.argv[:]
sys.argv = ['-b']
import ROOT
sys.argv = args
ROOT.gROOT.SetBatch(True)
ROOT.PyConfig.IgnoreCommandLineOptions = True

#from libPython.plotUtils import safeGetObject, safeOpenFile, createPlotDirAndCopyPhp, drawTH2
sys.path.append(os.getcwd() + "/libPython/")
from plotUtils import *


def checkFit(infile, outdir, fitName, hbins):
    hStatusPass = copy.deepcopy(hbins.Clone(f"{fitName}_pass_status"))
    hStatusPass.Reset("ICESM")
    hStatusPass.SetTitle(f"{fitName} pass")
    hStatusFail = copy.deepcopy(hbins.Clone(f"{fitName}_fail_status"))
    hStatusFail.Reset("ICESM")
    hStatusFail.SetTitle(f"{fitName} fail")
    
    hEdmPass = copy.deepcopy(hbins.Clone(f"{fitName}_pass_edm"))
    hEdmPass.Reset("ICESM")
    hEdmPass.SetTitle(f"{fitName} pass")
    hEdmFail = copy.deepcopy(hbins.Clone(f"{fitName}_fail_edm"))
    hEdmFail.Reset("ICESM")
    hEdmFail.SetTitle(f"{fitName} fail")
    
    nEtaBins = hStatusPass.GetNbinsX()
    nPtBins = hStatusPass.GetNbinsY()
    
    f = safeOpenFile(infile)
    for k in f.GetListOfKeys():
        name = k.GetName()
        if "_res" not in name:
            continue
        obj = safeGetObject(f, name, detach=False)
        nbin = int(name.split("_")[0].lstrip("bin"))
        neta = int((nbin % nEtaBins) + 1)
        npt = int((nbin / nEtaBins) + 1)
        if "_resP" in name:
            hStatusPass.SetBinContent(neta, npt, obj.status())
            hEdmPass.SetBinContent(neta, npt, obj.edm())
        else:
            hStatusFail.SetBinContent(neta, npt, obj.status())
            hEdmFail.SetBinContent(neta, npt, obj.edm())
    rootfileWithEffi.Close()

    canvas = ROOT.TCanvas("canvas","",800,800)

    maxStatus = int(hStatusPass.GetBinContent(hStatusPass.GetMaximumBin()))
    zrange = f" max={maxStatus}::-0.5,4.5"    

    drawTH2(hStatusPass, "Muon #eta", "Muon p_{T} (GeV)", f"Fit status {zrange}",
            hStatusPass.GetName(), plotLabel="ForceTitle", outdir=outdir, 
            draw_both0_noLog1_onlyLog2=1, passCanvas=canvas,
            palette=87, nContours=5, drawOption="colz")

    maxStatus = int(hStatusFail.GetBinContent(hStatusFail.GetMaximumBin()))
    zrange = f" max={maxStatus}::-0.5,4.5"    

    drawTH2(hStatusFail, "Muon #eta", "Muon p_{T} (GeV)", f"Fit status {zrange}",
            hStatusFail.GetName(), plotLabel="ForceTitle", outdir=outdir, 
            draw_both0_noLog1_onlyLog2=1, passCanvas=canvas,
            palette=87, nContours=5, drawOption="colz")

    drawTH2(hEdmPass, "Muon #eta", "Muon p_{T} (GeV)", "Fit edm::0,0.00001",
            hEdmPass.GetName(), plotLabel="ForceTitle", outdir=outdir, 
            passCanvas=canvas,
            palette=87, nContours=51, drawOption="colz")
    
    drawTH2(hEdmFail, "Muon #eta", "Muon p_{T} (GeV)", "Fit edm::0,0.00001",
            hEdmFail.GetName(), plotLabel="ForceTitle", outdir=outdir, 
            passCanvas=canvas,
            palette=87, nContours=51, drawOption="colz")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Diagnostic for fit status')
    parser.add_argument("infile", type=str, nargs=1, help="Input file")
    #parser.add_argument("outdir", type=str, nargs=1, help="Output folder to save plots")
    args = parser.parse_args()

    infile = args.infile[0]
    #outdir = args.outdir[0] 
    mainPath = os.path.dirname(infile) + "/"
    outdir = mainPath + "plots/checkFitStatus/"
    createPlotDirAndCopyPhp(outdir)    

    # get histogram to read binning, might need to do it differently if this file does not exist yet
    rootfileWithEffi = safeOpenFile(mainPath + "allEfficiencies_2D.root")
    htmp = safeGetObject(rootfileWithEffi, "SF2D_nominal", detach=True)
    rootfileWithEffi.Close()
    
    tag = "MC" if "_DY_" in infile else "Data"
    fitName = f"Eff{tag}_" + infile.split(".")[1]

    checkFit(infile, outdir, fitName, htmp)

