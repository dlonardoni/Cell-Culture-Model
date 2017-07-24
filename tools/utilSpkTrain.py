__author__ = 'dlonardoni'
from numpy import *  # instead use import numpy as np
import numpy as np
from scipy import io
from string import atoi
# from neuronpy.util.spiketrain import *
# from utility import flatlist,filepath
import os

TotalRecordingTime = 3600  # (s)
dt = 0.13  # (ms) - sampling time interval 0.13 for APS, 0.1 for classical MEA
TW = 5  # (ms) - not used !
mfrMax = 15  # (Hz) - maximum acceptable MFR
mfrMin = 0.1  # (Hz) - minumum acceptable MFR
mbrMin = 0.4  # burst/min - minumum acceptable MBR
RowChanMax = 64  # =8 for classical MEA, =64 for APS
PrintMessages = True
filenameMAT=''
''' Important notes
	===============
1)
	About common variable names used in the PyMEA modules:
	'SpkList' variable name of the list of channels ('x','y','spikes') loaded by LoadSpikeTrains
	'spikes' variable name of the 2xN structure (first row: channel number, second row: corresponding time stamp).
2)
	"Active electrodes" are defined as electrodes with MFR in the (mfrMin,mfrMax) range, electrode with MFR outside of this
	range are discarded by the load procedure LoadSpikeTrains
'''


def flatlist(Vett2Flat):
    # http://stackoverflow.com/questions/952914/making-a-flat-list-out-of-list-of-lists-in-python
    VettFlatted = np.array([item for sublist in Vett2Flat for item in sublist])
    return VettFlatted


def ReadMatFile(filename):
    return io.loadmat(filename)  # read a .mat file


def LoadSpikeTrains(filename, ReadHeader=True):
    """
		Read a single MAT file (sparse structure) generated by 3Brain sw

		filename:       MAT file to read
		ReadHeader:     True => dt, TotalRecordingTime are set from the header, if an error occurs global variables are taken
						False => global variables are taken
	"""
    global dt, TotalRecordingTime, filenameMAT
    filenameMAT = filename
    daktum = ReadMatFile(filename)
    SpkList = []

    if ReadHeader:
        try:
            dt = 1000 / daktum['SamplingFrequency'][0][0]
            TotalRecordingTime = daktum['StopFrame'][0][0] * dt / 1000.0
        except:
            print "Header information is missing in ", filename
            print "The global parameters:",
            print "TotalRecordingTime= ", TotalRecordingTime, " [seconds]",
            print "dt= ", dt, " [ms]",
            print "will therefore be adopted."

    for channel in daktum.keys():
        pos = channel.rfind('_')
        if (pos > 0) & (channel[0] == 'C'):
            if size(daktum[channel]):
                tk = daktum[channel].indices * dt
                mfr = len(tk) / float(TotalRecordingTime)
                if (mfr > mfrMin) & (mfr < mfrMax):
                    ch = {'spikes': tk, 'x': atoi(channel[2:pos]), 'y': atoi(channel[pos + 1:])}
                    SpkList.append(ch)

    return SpkList


def LoadSpikeTrains2(pathFolder='', filename='peakTrain_%d_%d', Tmax=600.0):
    """
		Read a series of MAT files, each is a specific channel.
		pathFolder  - where to find the filename*
		filename    - file name
		Tmax        - max time interval
	"""
    SpkList = []
    HVc = arange(1, RowChanMax + 1)  # range of H/V channels
    # ***********************
    print "This procedure still needs to be updated coherently to LoadSpikeTrains such to read dt,Tmax from mat file!!"
    # ***********************
    for x in HVc:
        for y in HVc:
            FileName = filename % (x, y)
            FileNamePath = pathFolder + FileName + '.mat'
            # check existance of the file
            if os.path.exists(FileNamePath):
                tk = flatlist(ReadMatFile(FileNamePath)[FileName]) * dt
                mfr = len(tk) / Tmax
                if (mfr > mfrMin) & (mfr < mfrMax):
                    ch = {'spikes': tk, 'x': x, 'y': y}
                    SpkList.append(ch)
    return SpkList


def FormatSpikeTrains(SpkList, SortFlag=True):
    """
		convert spike trains to the 2xn format with first/second row corresponding to #electrode/spike time
		SortFlag    True/False  if True cause spikes to be properly sorted
	"""
    spikes = zeros((2, 0))
    for spkTrain in SpkList:
        EleInd = int(RowChanMax * (spkTrain['x'] - 1) + spkTrain['y'])  # x,y start from 0 or 1? CHECK AGAIN
        ST = spkTrain['spikes']
        if SortFlag: ST.sort()
        L = len(ST)
        vtmp = zeros((2, L))
        vtmp[0, :] = repeat(EleInd, L)
        vtmp[1, :] = ST
        spikes = hstack((spikes, vtmp))
    return spikes


def SplitSpkList(SpkList):
    """
		The procedure splits the SpkList in two separate lists with spikes and electrode number
	"""
    spkTrainList = []
    for SL in SpkList:
        spkTrainList.append(SL['spikes'])
    EleNum = ElectrodeNumber(SpkList)
    return spkTrainList, EleNum


def SpikeTrainRaster(spikes):
    """
		Given spikes (2xn format) returns a list of separate spike trains for each electrode
		SIMILAR TO SplitSpkList BUT HAVE TO CHECK IT  (ALMOST NEVER USED!)
	"""
    EleNum = unique(array(spikes[0, :], 'int'))
    spkTrainList = []
    for ele in EleNum:
        spkTrainList.append(spikes[1, spikes[0, :] == ele])
    return spkTrainList, EleNum


def SpikeStatistics(spikes, TimeWindow=600.0, ISImax=100, spkMin=5, ISIhistMax=5000, ISIhistMin=0, ISIhistDT=50):
    """
		Computes statistics on spikes using the 2xn format.
		The first row corresponds to the spiking electrode (1..Nelemax) with the second row reflecting the corresponing
		spike stamp.
		*** Important Note ***
		The procedure accepts all given electrodes and does not perform any filtering on them. Thus all "accetable" electrodes
		(e.g. with MFR: minF=0.1<MFR<maxF=15) have to be prefiltered outside the procedure as already done in LoadSpikeTrains and
		LoadSpikeTrains2.
	"""
    spikes_unique = unique(spikes[0, :])  # obtain the list of electrodes involved
    Lsu = len(spikes_unique)

    mfrVett = zeros(Lsu)
    mbrVett = zeros(Lsu)
    mfibVett = zeros(Lsu)
    mbdVett = zeros(Lsu)
    randSpkVett = zeros(Lsu)
    isiXhist = arange(ISIhistMin, ISIhistMax + ISIhistDT, ISIhistDT)
    isiAll = []
    ele = -1
    if PrintMessages: print "Duration of recording set to ", TimeWindow, " seconds"
    for indST in spikes_unique:
        ele += 1
        indOfST = spikes[0, :] == indST  # indexes of the spikes
        # print indST,len(spikes[0,:]),sum(indOfST)
        ST = spikes[1, indOfST]
        # print "number of spikes ",len(ST)
        numspikes_ele = len(ST)
        # burst analysis
        ISI = diff(append(ST, ST[-1] + 1e6))  # add a fake element at the end to close last potential burst
        isiAll.append(ISI)
        indISI = where(ISI > ISImax)[0]
        LindISI = len(indISI)
        ibegin = 0
        numburst = 0
        burdurTotTime = 0
        numspikes_burst = 0
        for k in xrange(LindISI):
            iend = indISI[k]
            nspkburst = (iend - ibegin + 1)
            if nspkburst >= spkMin:
                numspikes_burst += nspkburst  # num spikes in burst
                burstdur = ST[iend] - ST[ibegin]  # ms
                burdurTotTime += burstdur
                numburst += 1
            ibegin = iend + 1

        randSpkVett[ele] = 100.0 * (
            numspikes_ele - numspikes_burst) / numspikes_ele  # "random spike %" (falling outside a burst)
        mfrVett[ele] = 1.0 * numspikes_ele / TimeWindow  # number of spikes / sec

        if numburst > 0:
            mbdVett[ele] = burdurTotTime / numburst  # burst duration (ms)
            mbrVett[ele] = 60.0 * numburst / TimeWindow  # number of burst / min
            mfibVett[ele] = 1000.0 * numspikes_burst / burdurTotTime
    isiAll = flatlist(isiAll)
    isiHist = histogram(isiAll, isiXhist)
    return [mfrVett, mbrVett, mfibVett, mbdVett, randSpkVett, isiHist]


def ElectrodeNumber(SpkList):
    """
		Given SpkList returns the corresponding electrode numbers
	"""
    EleNum = []
    for ch in SpkList:
        ele = RowChanMax * (ch['x'] - 1) + ch['y']
        EleNum.append(ele)
    return array(EleNum, 'int')


def XYcoord(EleNum):
    """
		Given the electrode number returns the (x,y) coordinates.
	"""
    coord = []
    for eleN in EleNum:
        x = int((eleN - 1) / RowChanMax) + 1
        y = eleN - RowChanMax * (x - 1)
        coord.append((x, y))
    return coord


def CompareElectrodes(EleNumSrc, EleNumDest):
    """
		returns how many electrodes "EleNumSrc" are part of "EleNumDest"
	"""
    compare = intersect1d(EleNumSrc, EleNumDest)
    return len(compare), compare


def ShowSpkStat(out):
    """
		Return spike statistics in a fruible way.
		out is the output of SpikeStatistics
		returns a suitable output variable
	"""
    mfr = out[0]
    mbr = out[1]
    mfib = out[2]
    mbd = out[3]
    randS = out[4]

    N = len(mfr)  # note: only active channels are considered i.e. with mfr in [mfrMin,mfrMax]
    sN = np.sqrt(N)
    if PrintMessages:
        print "#active-electrodes   MFR(Hz) SEM  MBR(#burst/min) SEM     MFIB(Hz) SEM     MBD(ms) SEM  random-spikes(%)"
    # number of active electrodes
    if PrintMessages: print N, "\t",
    # MFR
    mfr_S = np.asarray([np.mean(mfr), np.std(mfr) / sN])

    if PrintMessages: print "%5.4f %5.4f " % (mfr_S[0], mfr_S[1]), "\t",  # - burst analysis
    # MBR
    iG = mbr >= mbrMin
    sG = np.sum(iG)
    mbr_S = np.asarray([np.mean(mbr[iG]), np.std(mbr[iG]) / sG])
    if PrintMessages: print "%5.4g %5.4g " % (mbr_S[0], mbr_S[1]), "\t",  # MFIB
    mfib_S = np.asarray([np.mean(mfib[iG]), np.std(mfib[iG]) / sG])
    if PrintMessages: print "%5.4g %5.4g " % (mfib_S[0], mfib_S[1]), "\t",  # MBD
    mbd_S = np.asarray([np.mean(mbd[iG]), np.std(mbd[iG]) / sG])
    if PrintMessages: print "%5.4g %5.4g " % (mbd_S[0], mbd_S[1]), "\t",  # random spikes
    randS_S = np.asarray([np.mean(randS), np.std(randS) / sN])
    if PrintMessages: print "%5.4g %5.4g " % (randS_S[0], randS_S[1])
    return mfr_S, mbr_S, mfib_S, mbd_S, randS_S