### python specific import
import os
import pickle
import shutil
from multiprocessing import Pool
import datetime
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

ROOT.gInterpreter.ProcessLine(".O3")

from libPython.tnpClassUtils import tnpSample
from libPython.plotUtils import compileMacro, testBinning, safeGetObject, safeOpenFile

if "/RooCBExGaussShape_cc.so" not in ROOT.gSystem.GetLibraries():
    compileMacro("libCpp/RooCBExGaussShape.cc")
if "/RooCMSShape_cc.so" not in ROOT.gSystem.GetLibraries():
    compileMacro("libCpp/RooCMSShape.cc")
if "/histFitter_C.so" not in ROOT.gSystem.GetLibraries():
    compileMacro("libCpp/histFitter.C")

### tnp library
import libPython.binUtils  as tnpBiner
import libPython.rootUtils as tnpRoot
import libPython.fitUtils as fitUtils
        
parser = argparse.ArgumentParser()
parser.add_argument('--checkBins'  , action='store_true'  , help = 'check  bining definition')
parser.add_argument('--createBins' , action='store_true'  , help = 'create bining definition')
parser.add_argument('--createHists', action='store_true'  , help = 'create histograms')
parser.add_argument('--sample'     , default='all'        , help = 'create histograms (per sample, expert only)')
parser.add_argument('--altSig'     , action='store_true'  , help = 'alternate signal model fit')
#parser.add_argument('--noBkg'      , action='store_true'  , help = 'Use no background for alternate signal model fit (mainly for test in MC)')
parser.add_argument('--altBkg'     , action='store_true'  , help = 'alternate background model fit')
parser.add_argument('--doFit'      , action='store_true'  , help = 'fit sample (sample should be defined in settings.py)')
parser.add_argument('--mcSig'      , action='store_true'  , help = 'fit MC nom [to init fit params]')
parser.add_argument('--doPlot'     , action='store_true'  , help = 'plotting')
parser.add_argument('--sumUp'      , action='store_true'  , help = 'sum up efficiencies')
parser.add_argument('--iBin'       , dest = 'binNumber'   , type=int,  default=-1, help='bin number (to refit individual bin)')
parser.add_argument('--flag'       , default = None       , help ='WP to test')
parser.add_argument('--era'        , type=str, default = '', choices=["BtoF", "GtoH"], help ='era to perform tnp fits for')
parser.add_argument('--inputMC'    , type=str, default = '', help = "MC input file which contains 3d histograms")
parser.add_argument('--inputData'  , type=str, default = '', help = "Data input file which contains 3d histograms")
parser.add_argument('--outdir'     , type=str, default=None,
                    help="name of the output folder (if not passed, a default one is used, which has the time stamp in it)")
parser.add_argument('--useTrackerMuons', action='store_true'  , help = 'Measuring efficiencies specific for tracker muons (different tunings needed')

args = parser.parse_args()

if args.flag is None:
    print('[tnpEGM_fitter] flag is MANDATORY, this is the working point as defined in the settings.py')
    sys.exit(0)

## put most of the stuff here and make it configurable...
## ===========================================================================

massbins, massmin, massmax = 60, 60, 120

## define the binning here, much easier...
binning_eta = [round(-2.4+0.1*i,2) for i in range(49) ]
#binning_eta = [-2.4+0.1*i for i in range(4) ]
#binning_eta = [-2.4, -2.25, -2.10, -1.95, -1.8, -1.7, -1.:q
#binning_eta = [0.+0.2*i for i in range(13) ]

#binning_pt  = [25., 35., 45., 55., 65.]#27.5, 30., 32., 34, 36., 38., 40., 42., 44., 47., 50., 55., 65]
binning_pt  = [24., 26., 28., 30., 32., 34., 36., 38., 40., 42., 44., 47., 50., 55., 60., 65.]
#binning_pt  = [24., 26., 28., 30.]

#binning_pt  = [-15., -7.5, -5., -2.5, 0., 2.5, 5., 7.5, 15.]  ## ALERT


typeflag = args.flag.split('_')[1]

print("typeflag = ",typeflag)

if typeflag == 'tracking':
    #binning_pt  = [15., 25.,35.,45.,55.,65.,80.]
    #massbins, massmin, massmax = 100, 40, 140
    #binning_pt  = [55., 65.]
    binning_pt  = [25., 35., 45., 55., 65.]  # [24., 65.]
    #massbins, massmin, massmax = 100, 50, 150
    massbins, massmin, massmax = 80, 50, 130
    binningDef = {
        'eta' : {'var' : 'eta', 'type': 'float', 'bins': binning_eta},
        'pt'  : {'var' : 'pt' , 'type': 'float', 'bins': binning_pt }
    }

elif typeflag == 'reco':
    #binning_pt   = [24., 65.]
    massbins, massmin, massmax = 52, 68, 120
    if args.useTrackerMuons:
        binning_pt  = [24., 26., 30., 34., 38., 42., 46., 50., 55., 65.]
    else:
        binning_pt  = [24., 26., 30., 34., 38., 42., 46., 50., 55., 60., 65.]
    #binning_pt  = [24., 26., 28., 30., 32., 34., 36., 38., 40., 42., 44., 47., 50., 55., 60., 65.]
    binningDef = {
        'eta' : {'var' : 'eta', 'type': 'float', 'bins': binning_eta},
        'pt'  : {'var' : 'pt' , 'type': 'float', 'bins': binning_pt }
    }

elif typeflag == 'veto':
    binning_pt = [(15. + 5.*i) for i in range(11)]
    binningDef = {
        'eta' : {'var' : 'eta', 'type': 'float', 'bins': binning_eta},
        'pt'  : {'var' : 'pt' , 'type': 'float', 'bins': binning_pt }
    }

else:
    binningDef = {
        'eta' : {'var' : 'eta', 'type': 'float', 'bins': binning_eta},
        'pt'  : {'var' : 'pt' , 'type': 'float', 'bins': binning_pt }
    }


#############################################################
########## fitting params to tune fit by hand if necessary
#############################################################
if typeflag == 'tracking':

    bkgParFit = [
        "expalphaP[0.,-5.,5.]",
        "expalphaF[0.,-5.,5.]",
        "acmsF[60.,40.,130.]","betaF[0.05,0.01,0.11]","gammaF[0.1, 0, 1]","peakF[90.0]",
        "c1F[0.0,-1.0,1.0]","c2F[-0.5,-1.0,1.0]","c3F[0.0,-1.0,1.0]","c4F[-0.5,-1.0,1.0]"
    ]
    bkgShapes = [
        "Exponential::bkgPass(x, expalphaP)",
        #"RooCMSShape::bkgPass(x, acmsP, betaP, gammaP, peakP)",
        "RooCMSShape::bkgFail(x, acmsF, betaF, gammaF, peakF)",
        "Chebychev::bkgFailBackup(x,{c1F,c2F,c3F,c4F})",
        #"Bernstein::bkgFailBackup(x,{b0F[0.5,0,1.0],b1F[0.5,0,1.0],b2F[0.5,0,1.0],b3F[0.5,0,1.0],b4F[0.5,0,1.0]})",
        #"Exponential::bkgFailBackup(x, expalphaF)"
    ]
    
    tnpParNomFit = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[0.5,0.1,5.0]",
        "meanF[-0.0,-5.0,5.0]","sigmaF[0.5,0.05,3.0]",
    ]

    # these might be partially overridden when running the fit to data by taking the values from the MC fit and narrowing the range in which they can float to help convergence
    tnpParAltSigFit = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[1,0.7,6.0]","alphaP[2.0,1.2,3.5]",'nP[3,-5,5]',"sigmaP_2[1.5,0.5,6.0]",
        "meanF[-0.0,-12.0,12.0]","sigmaF[2,0.7,12.0]","alphaF[2.0,1.2,3.5]",'nF[3,-5,5]',"sigmaF_2[2.0,0.5,6.0]",
    ]

    # for pt >= 55 and tracking (se also note above)
    tnpParAltSigFitTrackingHighPt = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[1,0.7,6.0]","alphaP[2.0,1.2,3.5]",'nP[3,-5,5]',"sigmaP_2[1.5,0.5,6.0]",
        "meanF[4.0,-1.0,15.0]","sigmaF[2,0.7,15.0]","alphaF[2.0,1.2,3.5]",'nF[3,-5,5]',"sigmaF_2[2.0,0.5,6.0]",
    ]

    tnpParNomFit.extend(bkgParFit)
    tnpParAltSigFit.extend(bkgParFit)
    tnpParAltSigFitTrackingHighPt.extend(bkgParFit)
    
    if not args.mcSig:
        if args.useTrackerMuons:
            # for tracker muons the fraction is much larger
            tnpParNomFit.extend(["maxFracSigF[0.5]"])
            tnpParAltSigFit.extend(["maxFracSigF[0.5]"])
            tnpParAltSigFitTrackingHighPt.extend(["maxFracSigF[0.5]"])
        else:
            tnpParNomFit.extend(["maxFracSigF[0.15]"])
            tnpParAltSigFit.extend(["maxFracSigF[0.15]"])
            tnpParAltSigFitTrackingHighPt.extend(["maxFracSigF[0.15]"])

    # ## Try to constrain some background parameters (for tracking might need to do it for signal instead, since S/B is small)
    parConstraints = [
        # Passing
        #"Gaussian::constrainP_acmsP(acmsP,90,50)",
        #"Gaussian::constrainP_betaP(betaP,0.05,0.25)",
        #"Gaussian::constrainP_gammaP(gammaP,0.5,0.8)",
        # failing
        "Gaussian::constrainF_acmsF(acmsF,90,50)",
        "Gaussian::constrainF_betaF(betaF,0.05,0.25)",
        "Gaussian::constrainF_gammaF(gammaF,0.5,0.8)",
    ]

            
elif typeflag == 'reco':

    ## when forming the workspace in fitUtils.py the parameter with LOWPT or HIGHPT will be renamed without this keyword depending on pt >= 40
    bkgParFit = [
        "expalphaP[0.,-5.,5.]",
        "expalphaF[0.,-5.,5.]",
        "acmsF[60.,40.,130.]","betaF[0.05,0.005,0.12]","gammaF[0.1, 0, 1]","peakF[90.0]",
    ]
    bkgShapes = [
        "Exponential::bkgPass(x, expalphaP)",
        #"RooCMSShape::bkgPass(x, acmsP, betaP, gammaP, peakP)",
        "RooCMSShape::bkgFail(x, acmsF, betaF, gammaF, peakF)",
        #"Bernstein::bkgFailBackup(x,{c0F[0.5,0,1.0],c1F[0.5,0,1.0],c2F[0.5,0,1.0],c3F[0.5,0,1.0],c4F[0.5,0,1.0]})",
        "Exponential::bkgFailBackup(x, expalphaF)"
        #"Chebychev::bkgFailBackup(x,{c1F[0.0,-1.0,1.0],c2F[-0.5,-1.0,1.0],c3F[0.0,-1.0,1.0],c4F[-0.5,-1.0,1.0]})",
    ]

    tnpParNomFit = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[0.5,0.1,3.0]",
        "meanF[-0.0,-3.0,3.0]","sigmaF[0.5,0.01,2.0]",
    ]
    
    # was to tune few bins for reco, but currently used everywhere
    tnpParAltSigFit = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[1,0.7,6.0]","alphaP[2.0,1.2,3.5]",'nP[3,-5,5]',"sigmaP_2[1.5,0.5,6.0]",
        "meanF[-0.0,-5.0,5.0]","sigmaF[2,0.7,5.0]","alphaF[2.0,1.2,3.5]",'nF[3,-5,5]',"sigmaF_2[2.0,0.5,6.0]",
    ]

    tnpParNomFit.extend(bkgParFit)
    tnpParAltSigFit.extend(bkgParFit)

    
    if not args.mcSig and args.useTrackerMuons:
        # for tracker muons
        tnpParNomFit.extend(["maxFracSigF[0.05]"] if args.binNumber in [24] else ["maxFracSigF[0.05]"] if args.binNumber in [50, 69, 79, 133, 420] else ["maxFracSigF[0.3]"])
        tnpParAltSigFit.extend(["maxFracSigF[0.1]"] if args.binNumber in [29] else ["maxFracSigF[0.3]"])

    # ## Try to constrain some background parameters (for tracking might need to do it for signal instead, since S/B is small)
    parConstraints = [
        # Passing
        #"Gaussian::constrainP_acmsP(acmsP,90,50)",
        #"Gaussian::constrainP_betaP(betaP,0.05,0.25)",
        #"Gaussian::constrainP_gammaP(gammaP,0.5,0.8)",
        # failing
        #"Gaussian::constrainF_acmsF(acmsF,90,50)",
        #"Gaussian::constrainF_betaF(betaF,0.05,0.25)",
        #"Gaussian::constrainF_gammaF(gammaF,0.5,0.8)",
    ]

else:
    
    bkgParFit = [
        "expalphaP[0.,-5.,5.]",
        "expalphaF[0.,-5.,5.]",
        "acmsF[60.,40.,130.]","betaF[0.05,0.01,0.11]","gammaF[0.1, 0, 1]","peakF[90.0]",
        "c1F[0.0,-1.0,1.0]","c2F[-0.5,-1.0,1.0]","c3F[0.0,-1.0,1.0]"
    ]
    bkgShapes = [
        "Exponential::bkgPass(x, expalphaP)",
        "Exponential::bkgFail(x, expalphaF)",
        "Chebychev::bkgFailBackup(x,{c1F,c2F,c3F})",
     ]

    tnpParNomFit = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[0.5,0.1,5.0]",
        "meanF[-0.0,-5.0,5.0]","sigmaF[0.5,0.1,5.0]",
    ]
    
    tnpParAltSigFit = [
        "meanP[-0.0,-5.0,5.0]","sigmaP[1,0.7,6.0]","alphaP[2.0,1.2,3.5]",'nP[3,-5,5]',"sigmaP_2[1.5,0.5,6.0]",
        "meanF[-0.0,-5.0,5.0]","sigmaF[2,0.7,15.0]","alphaF[2.0,1.2,3.5]",'nF[3,-5,5]',"sigmaF_2[2.0,0.5,6.0]",
    ]

    parConstraints = []

        
# add second gaussian at low mass around 70 to model FSR bump for working points with isolation
flagsWithFSR = ["iso", "trigger", "isonotrig"]
if any(x in typeflag for x in flagsWithFSR):
    fsrGauss = ["fsrMeanF[70.0,65.0,80.0]", "fsrSigmaF[1.0,1.2,5.0]"]
    tnpParAltSigFit.extend(fsrGauss)

# for now this is not used, the nominal background model has been moved to exponential already, this might become a Bernstein polynominal or something
tnpParAltBkgFit = [
    "meanP[-0.0,-5.0,5.0]","sigmaP[0.5,0.1,5.0]",
    "meanF[-0.0,-10.0,10.0]","sigmaF[0.5,0.1,5.0]",
    "expalphaP[0.,-5.,5.]",
    "expalphaF[0.,-5.,5.]",
    ]

if args.outdir:
    baseOutDir = '{o}/efficiencies_{era}/'.format(o=args.outdir, era=args.era)
else:
    today = datetime.date.isoformat(datetime.date.today())
    baseOutDir = 'plots/results_2022-09-28_binnedInPtEta_4ptbins25to65_noOScharge/efficiencies_{era}/'.format(d=today, era=args.era)

outputDirectory = '%s/%s/' % (baseOutDir, args.flag)

print('===>  Output directory: ')
print(outputDirectory)

luminosity = 16.8 if args.era == "GtoH" else 19.5
dataName = f"mu_Run{args.era}"
samples_data = tnpSample(dataName,
                         args.inputData,
                         f"{outputDirectory}/{dataName}_{args.flag}.root",
                         False,
                         luminosity)

eraMC = "postVFP" if args.era == "GtoH" else "preVFP"
mcName = f"mu_DY_{eraMC}"
samples_dy = tnpSample(mcName,
                       args.inputMC,
                       f"{outputDirectory}/{mcName}_{args.flag}.root",
                       True,
                       luminosity)
#samples_data.printConfig()
#samples_dy.printConfig()

## check binning in histogram and consistency with settings above
## FIXME: should be done for each step, but histograms are not always passed
if args.createHists:
    ftest = ROOT.TFile(args.inputData, "read")
    htest = ftest.Get(f"pass_{dataName}")
    if massmin < htest.GetXaxis().GetBinLowEdge(1) or massmax > htest.GetXaxis().GetBinLowEdge(htest.GetNbinsX()+1):
        print(f"Error: you are trying to use a wider mass range ({massmin}-{massmax}) than the histograms for {typeflag}")
        quit()
    this_binning_pt = [round(htest.GetYaxis().GetBinLowEdge(i), 1) for i in range(1, htest.GetNbinsY()+2) ]
    testBinning(binning_pt, this_binning_pt, "pt", typeflag)
    this_binning_eta = [round(htest.GetZaxis().GetBinLowEdge(i), 1) for i in range(1, htest.GetNbinsZ()+2) ]
    testBinning(binning_eta, this_binning_eta, "eta", typeflag)
    ftest.Close()

samplesDef = {
    'data'   : samples_data,
    'mcNom'  : samples_dy,
    'mcAlt'  : None, 
    'tagSel' : None,
}

#samplesDef["data"].printConfig()

## done making it more configurable
## ===========================================================================================

####################################################################
##### Create (check) Bins
####################################################################
if args.checkBins:
    print(">>> check bins")
    tnpBins = tnpBiner.createBins(binningDef, None)
    for ib in range(len(tnpBins['bins'])):
        print(tnpBins['bins'][ib]['name'])
        print('  - cut: ',tnpBins['bins'][ib]['cut'])
    sys.exit(0)

if args.createBins:
    print(">>> create bins")
    if os.path.exists( outputDirectory ):
        shutil.rmtree( outputDirectory )
    os.makedirs( outputDirectory )
    tnpBins = tnpBiner.createBins(binningDef, None)
    pickle.dump( tnpBins, open( '%s/bining.pkl'%(outputDirectory),'wb') )
    print('created dir: {o} '.format(o= outputDirectory))
    print('bining created successfully... ')
    print('Note than any additional call to createBins will overwrite directory {o}'.format(o= outputDirectory))
    sys.exit(0)

tnpBins = pickle.load( open( '%s/bining.pkl'%(outputDirectory),'rb') )

#print(tnpBins)
#quit()


####################################################################
##### Create Histograms
####################################################################

if args.createHists:
    print(">>> create histograms")
    def parallel_hists(sampleType):
        # if not sampleType == 'mcNom': return
        sample = samplesDef[sampleType]
        if sample is not None and (sampleType == args.sample or args.sample == 'all'):
            print('creating histogram for sample', sample.getName())
            sample.printConfig()
            if typeflag == 'tracking':
                var = { 'namePassing' : 'pair_mass', 'nameFailing' : 'pair_massStandalone', 'nbins' : massbins, 'min' : massmin, 'max': massmax }
            else:
                var = { 'name' : 'pair_mass', 'nbins' : massbins, 'min' : massmin, 'max': massmax }
            tnpRoot.makePassFailHistograms(sample, tnpBins['bins'], binningDef, var)

    pool = Pool()
    pool.map(parallel_hists, samplesDef.keys())
    sys.exit(0)


####################################################################
##### Actual Fitter
####################################################################
sampleToFit = samplesDef['data']
if sampleToFit is None:
    print('[tnpEGM_fitter, prelim checks]: sample (data or MC) not available... check your settings')
    sys.exit(1)

sampleMC = samplesDef['mcNom']
if sampleMC is None:
    print('[tnpEGM_fitter, prelim checks]: MC sample not available... check your settings')
    sys.exit(1)
    
for s in samplesDef.keys():
    sample =  samplesDef[s]
    if sample is None: continue
    setattr( sample, 'mcRef'     , sampleMC )
    setattr( sample, 'nominalFit', '%s/%s_%s.nominalFit.root' % ( outputDirectory , sample.getName(), args.flag ) )
    setattr( sample, 'altSigFit' , '%s/%s_%s.altSigFit.root'  % ( outputDirectory , sample.getName(), args.flag ) )
    setattr( sample, 'altBkgFit' , '%s/%s_%s.altBkgFit.root'  % ( outputDirectory , sample.getName(), args.flag ) )

### change the sample to fit if mc fit
if args.mcSig:
    sampleToFit = samplesDef['mcNom']

if  args.doFit:
    print(">>> running fits")
    #print('sampleToFit.dump()', sampleToFit.dump())
    useAllTemplateForFail = True # if typeflag in ["reco", "tracking"] else False # use all probes to build MC template for failing probes when fitting data nominal
    maxFailIntegralToUseAllProbe = 300 if typeflag not in ["tracking"] else -1 # use all probes for the failing template only when stat is very small, otherwise sometimes the fit doesn't work well
    altSignalFail = True if typeflag in ["reco", "tracking", "veto"] else False # use Gaussian as resolution function for altSig model
    modelFSR = True if typeflag in flagsWithFSR else False # add Gaussian to model low mass bump from FSR, in altSig fit
    def parallel_fit(ib): ## parallel
        #print("tnpBins['bins'][ib] = ",tnpBins['bins'][ib])
        if (args.binNumber >= 0 and ib == args.binNumber) or args.binNumber < 0:
            if args.altSig:
                if typeflag == 'tracking':
                    # constrainSignalFailFromMC sets the data fit parameters to MC value +/- 3*uncertainty
                    if fitUtils.ptMin(tnpBins['bins'][ib]) > 54.0: # force peak mean more on the right for high pt bins and tracking efficiency
                        fitUtils.histFitterAltSig(sampleToFit, tnpBins['bins'][ib], tnpParAltSigFitTrackingHighPt, massbins, massmin, massmax,
                                                  altSignalFail=altSignalFail, modelFSR=False, constrainSignalFailFromMC=False, constrainPars=parConstraints, bkgShapes=bkgShapes)
                    else:
                        fitUtils.histFitterAltSig(sampleToFit, tnpBins['bins'][ib], tnpParAltSigFit, massbins, massmin, massmax,
                                                  altSignalFail=altSignalFail, modelFSR=False, constrainSignalFailFromMC=False, constrainPars=parConstraints, bkgShapes=bkgShapes)
                elif typeflag == 'reco': 
                    fitUtils.histFitterAltSig(sampleToFit, tnpBins['bins'][ib], tnpParAltSigFit, massbins, massmin, massmax,
                                              altSignalFail=altSignalFail, modelFSR=False, constrainPars=parConstraints, bkgShapes=bkgShapes)
                else:
                    #fitUtils.histFitterAltSig(sampleToFit, tnpBins['bins'][ib], tnpParAltSigFit, massbins, massmin, massmax,
                    #                          altSignalFail=altSignalFail, modelFSR=modelFSR, zeroBackground=True)
                    fitUtils.histFitterAltSig(sampleToFit, tnpBins['bins'][ib], tnpParAltSigFit, massbins, massmin, massmax,
                                              altSignalFail=altSignalFail, modelFSR=modelFSR, constrainPars=parConstraints, bkgShapes=bkgShapes)
            elif not args.mcSig:
                # do this only for data
                if args.altBkg:
                    fitUtils.histFitterAltBkg(sampleToFit, tnpBins['bins'][ib], tnpParAltBkgFit, massbins, massmin, massmax,
                                              useAllTemplateForFail, maxFailIntegralToUseAllProbe, bkgShapes=bkgShapes)
                else:
                    fitUtils.histFitterNominal(sampleToFit, tnpBins['bins'][ib], tnpParNomFit, massbins, massmin, massmax,
                                               useAllTemplateForFail, maxFailIntegralToUseAllProbe, constrainPars=parConstraints, bkgShapes=bkgShapes)
            # else:
            #     # nominal fit in MC still with analytc form but no background
            #     fitUtils.histFitterAltSig(sampleToFit, tnpBins['bins'][ib], tnpParAltSigFit, massbins, massmin, massmax,
            #                               altSignalFail=altSignalFail, modelFSR=modelFSR, zeroBackground=True)
                    
    pool = Pool() ## parallel
    pool.map(parallel_fit, range(len(tnpBins['bins']))) ## parallel

    args.doPlot = True

####################################################################
##### dumping plots
####################################################################
if  args.doPlot:
    fileName = sampleToFit.nominalFit
    fitType  = 'nominalFit'
    if args.altSig :
        fileName = sampleToFit.altSigFit
        fitType  = 'altSigFit'
    if args.altBkg :
        fileName = sampleToFit.altBkgFit
        fitType  = 'altBkgFit'

    # if doing one bin get the new plots and update the file, don't overwrite it or all other bins are lost
    if args.binNumber >= 0:
        thisbin = tnpBins['bins'][args.binNumber]['name']
        rootfileBin = safeOpenFile(f"{fileName}_bin_{thisbin}")
        rootfile = safeOpenFile(f"{fileName}", mode="UPDATE")
        for k in rootfileBin.GetListOfKeys():
            obj = safeGetObject(rootfileBin, k.GetName(), detach=False)
            obj.Write(k.GetName(), ROOT.TObject.kOverwrite) # write in merged root file overwriting keys if they already existed
        rootfile.Close()
        rootfileBin.Close()
        os.system('rm '+fileName+'_bin_bin*')
    else:
        os.system('hadd -f %s %s' % (fileName, fileName+'_bin_bin*'))
        os.system('sleep 1')
        os.system('rm '+fileName+'_bin_bin*')

    plottingDir = '%s/plots/%s/%s' % (outputDirectory,sampleToFit.getName(),fitType)
    if not os.path.exists( plottingDir ):
        os.makedirs( plottingDir )
    shutil.copy('etc/inputs/index.php.listPlots','%s/index.php' % plottingDir)

    verbosePlotting = True
    rootfile = safeOpenFile(f"{fileName}")
    for ib in range(len(tnpBins['bins'])):
        if (args.binNumber >= 0 and ib == args.binNumber) or args.binNumber < 0:
            tnpRoot.histPlotter(rootfile, tnpBins['bins'][ib], plottingDir, -1, verbosePlotting ) ## the -1 is form marc, something with replica
    rootfile.Close()
    print(' ===> Plots saved in <=======')
#    print('localhost/%s/' % plottingDir)


####################################################################
##### dumping egamma txt file
####################################################################
if args.sumUp:
    from pprint import pprint
    #print('this is the dump of sampleToFit:')
    #sampleToFit.dump()
    #pprint(vars(sampleToFit.mcRef))
    #print('done with dump')
    info = {
        'data'        : sampleToFit.getOutputPath(),
        'dataNominal' : sampleToFit.nominalFit,
        'dataAltSig'  : sampleToFit.altSigFit ,
        'dataAltBkg'  : sampleToFit.altBkgFit ,
        'mcNominal'   : sampleToFit.mcRef.getOutputPath(),
        'mcNominal_fit'   : sampleToFit.mcRef.nominalFit,
        ## marc 'mcAlt'       : None,
        'mcAlt'       : sampleToFit.mcRef.altSigFit,
        'mcAltBkg'    : sampleToFit.mcRef.altBkgFit,
        'tagSel'      : None
        }

    if not samplesDef['mcAlt'] is None:
        info['mcAlt'] = samplesDef['mcAlt'].getOutputPath()
    if not samplesDef['tagSel'] is None:
        info['tagSel'] = samplesDef['tagSel'].getOutputPath()

    #print(info)

    effis = None
    effFileName = outputDirectory+'/allEfficiencies.txt'
    fOut = open( effFileName,'w')

    def parallel_sumUp(_bin):
        effis = tnpRoot.getAllEffi( info, _bin )
        #print("effis =",effis)
        #print('this is _bin', _bin)

        ### formatting assuming 2D bining -- to be fixed
        v1Range = _bin['title'].split(';')[1].split('<')
        v2Range = _bin['title'].split(';')[2].split('<')

        ib = int(_bin['name'].split('_')[0].replace('bin',''))

        fOut = open(effFileName+'_tmpTMP_'+str(ib), 'w')

        if not ib:
            astr = '### var1 : %s\n' % v1Range[1]
            fOut.write( astr )
            astr = '### var2 : %s\n' % v2Range[1]
            fOut.write( astr )
            exp = '{v0:8s}\t{v1:8s}\t{v2:8s}\t{v3:8s}\t{edv:10s}\t{ede:10s}\t{emcv:10s}\t{emce:10s}\t{edalts:15s}\t{edaltse:15s}\t{emcalt:15s}\t{emcalte:15s}\t{edaltb:15s}\t{etagsel:10s}\n'.format(
                v0='var1min', v1='var1max', v2='var2min', v3='var2max',
                edv='eff data', ede='err data',
                emcv='eff mc', emce='err mc',
                edalts='eff data altS', edaltse='err data altS',
                emcalt='eff mc alt', emcalte='err mc alt', edaltb='eff data altB', etagsel='eff tag sel')
            #print(exp)
            fOut.write(exp)

        astr =  '%-+8.3f\t%-+8.3f\t%-+8.3f\t%-+8.3f\t%-10.5f\t%-10.5f\t%-10.5f\t%-10.5f\t%-15.5f\t%-15.5f\t%-15.5f\t%-15.5f\t%-15.5f\t%-10.5f' % (
            float(v1Range[0]), float(v1Range[2]),
            float(v2Range[0]), float(v2Range[2]),
            effis['dataNominal'][0],effis['dataNominal'][1],
            effis['mcNominal'  ][0],effis['mcNominal'  ][1],
            effis['dataAltSig' ][0],effis['dataAltSig' ][1],
            effis['mcAlt' ][0], effis['mcAlt' ][1],
            effis['dataAltBkg' ][0],
            effis['tagSel'][0],
            )
        #print(astr)
        fOut.write( astr + '\n' )

        fOut.close()

        canv_all = ROOT.TCanvas(_bin['name'], _bin['name'], 1200, 1200)
        canv_all.Divide(3,3)
        canv_all.Draw()
        ipad = 1
        canv_all.cd(0)
        txt = ROOT.TLatex()
        txt.SetTextFont(42)
        txt.SetTextSize(0.03)
        txt.SetNDC()
        txt.DrawLatex(0.01, 0.97, '{n}'.format(n=_bin['name'].replace('_',' ').replace('To', '-').replace('probe ', '').replace('m','-').replace('pt','XX').replace('p','.').replace('XX','p_{T}')))
        txt.SetTextSize(0.08)
        for ip, p in enumerate(effis['canv_mcAlt'].GetListOfPrimitives()):
            if not ip: continue
            canv_all.cd(ipad)
            p.SetPad(0.05, 0.00, 0.95, 0.90)
            p.Draw()
            ipad+=1
        canv_all.cd(ipad)
        txt.SetTextFont(62)
        txt.DrawLatex(0.00, 0.85, 'MC counting efficiency:')
        txt.SetTextFont(42)
        tmp = effis['mcNominal']
        txt.DrawLatex(0.10, 0.75, 'passing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[2],ne=tmp[4]))
        txt.DrawLatex(0.10, 0.64, 'failing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[3],ne=tmp[5]))
        txt.SetTextFont(62)
        txt.DrawLatex(0.10, 0.53, 'efficiency: {e:.2f} #pm {ee:.2f} %'.format(e=tmp[0]*100., ee=tmp[1]*100.))
        txt.SetTextFont(42)
        tmp = effis['mcAlt']
        txt.SetTextFont(62)
        txt.DrawLatex(0.00, 0.35, 'MC fitted signal:')
        txt.SetTextFont(42)
        txt.DrawLatex(0.10, 0.24, 'passing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[2],ne=tmp[4]))
        txt.DrawLatex(0.10, 0.13, 'failing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[3],ne=tmp[5]))
        txt.SetTextFont(62)
        txt.DrawLatex(0.10, 0.02, 'efficiency: {e:.2f} #pm {ee:.2f} %'.format(e=tmp[0]*100., ee=tmp[1]*100.))
        txt.SetTextFont(42)
        ipad+=1
        for ip, p in enumerate(effis['canv_dataNominal'].GetListOfPrimitives()):
            if not ip: continue
            canv_all.cd(ipad)
            p.SetPad(0.05, 0.00, 0.95, 0.90)
            p.Draw()
            ipad+=1
        canv_all.cd(ipad)
        tmp = effis['dataNominal']
        txt.SetTextFont(62)
        txt.DrawLatex(0.00, 0.65, 'data nominal:')
        txt.SetTextFont(42)
        txt.DrawLatex(0.10, 0.54, 'passing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[2],ne=tmp[4]))
        txt.DrawLatex(0.10, 0.43, 'failing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[3],ne=tmp[5]))
        txt.SetTextFont(62)
        txt.DrawLatex(0.10, 0.32, 'efficiency: {e:.2f} #pm {ee:.2f} %'.format(e=tmp[0]*100., ee=tmp[1]*100.))
        txt.SetTextFont(42)
        ipad+=1
        for ip, p in enumerate(effis['canv_dataAltSig'].GetListOfPrimitives()):
            if not ip: continue
            canv_all.cd(ipad)
            p.SetPad(0.05, 0.00, 0.95, 0.90)
            p.Draw()
            ipad+=1
        canv_all.cd(ipad)
        tmp = effis['dataAltSig']
        txt.SetTextFont(62)
        txt.DrawLatex(0.00, 0.65, 'data alternative:')
        txt.SetTextFont(42)
        txt.DrawLatex(0.10, 0.54, 'passing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[2],ne=tmp[4]))
        txt.DrawLatex(0.10, 0.43, 'failing: {n:.1f} #pm {ne:.1f}'.format(n=tmp[3],ne=tmp[5]))
        txt.SetTextFont(62)
        txt.DrawLatex(0.10, 0.32, 'efficiency: {e:.2f} #pm {ee:.2f} %'.format(e=tmp[0]*100., ee=tmp[1]*100.))
        txt.SetTextFont(42)

        #effis['canv_dataAltSig'].Draw()

        odllevel = ROOT.gErrorIgnoreLevel
        ROOT.gErrorIgnoreLevel = ROOT.kWarning
        canv_all.SaveAs(outputDirectory+'/plots/{n}_all.pdf'.format(n=_bin['name']))
        canv_all.SaveAs(outputDirectory+'/plots/{n}_all.png'.format(n=_bin['name']))
        ROOT.gErrorIgnoreLevel = odllevel
    
    pool = Pool()
    pool.map(parallel_sumUp, tnpBins['bins'])
    #parallel_sumUp(tnpBins['bins'])

    lsfiles = []
    alltmpfiles = os.listdir(outputDirectory)
    for ifile in alltmpfiles:
        if not 'tmpTMP' in ifile: continue
        lsfiles.append(outputDirectory+'/'+ifile)

    lsfiles = sorted(lsfiles, key = lambda x: int(x.split('_')[-1]))
    #print(lsfiles)

    os.system('cat '+' '.join(lsfiles)+' > '+effFileName)
    os.system('rm  '+' '.join(lsfiles))

    os.system('cp etc/inputs/index.php {d}/index.php'.format(d=outputDirectory+'/plots/'))


    #fOut.close()

    print('Efficiencies saved in file : ',  effFileName)
    import libPython.EGammaID_scaleFactors as makesf
    makesf.doSFs(effFileName,luminosity,['pt', 'eta'], outputDirectory+'/plots/')
    ## put here the new file for marco
